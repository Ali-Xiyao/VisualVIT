from __future__ import annotations

from collections import defaultdict
import hashlib
from typing import Any, Mapping, Sequence

import torch
import torch.nn.functional as F


DYNAMIC_LABELS = frozenset(("Improved", "Worse", "New", "Resolved"))


def stable_hash(*parts: object) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def transition_examples(
    pair_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    examples = []
    for row in pair_rows:
        for annotation in row.get("transition_supervision", []):
            label = str(annotation["label"])
            examples.append(
                {
                    "example_id": stable_hash(
                        "r37-transition-example-v1",
                        row["pair_id"],
                        annotation["finding"],
                        label,
                    ),
                    "pair_id": str(row["pair_id"]),
                    "patient_id": str(row["patient_id"]),
                    "partition": str(row["partition"]),
                    "finding": str(annotation["finding"]),
                    "label": label,
                    "current_view": str(row["current_view"]),
                    "prior_dicom_id": str(row["prior_dicom_id"]),
                    "current_dicom_id": str(row["current_dicom_id"]),
                }
            )
    return sorted(examples, key=lambda item: item["example_id"])


def build_cmcp_matches(
    examples: Sequence[Mapping[str, str]],
    current_embeddings: Mapping[str, torch.Tensor],
    *,
    chunk_size: int = 512,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if chunk_size <= 0:
        raise ValueError("chunk size must be positive")
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for raw in examples:
        item = {key: str(value) for key, value in raw.items()}
        key = (item["partition"], item["finding"], item["current_view"])
        groups[key].append(item)

    matches: list[dict[str, Any]] = []
    dynamic_total = 0
    missing_embeddings = set()
    group_diagnostics = {}
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda item: item["example_id"])
        vectors = []
        valid_rows = []
        for row in rows:
            vector = current_embeddings.get(row["current_dicom_id"])
            if vector is None:
                missing_embeddings.add(row["current_dicom_id"])
                continue
            if vector.ndim != 1:
                raise ValueError("CMCP embeddings must be one-dimensional")
            valid_rows.append(row)
            vectors.append(vector.to(dtype=torch.float32, device="cpu"))
        if not vectors:
            continue
        matrix = F.normalize(torch.stack(vectors, dim=0), dim=-1)
        group_dynamic = sum(
            row["label"] in DYNAMIC_LABELS for row in valid_rows
        )
        group_matched = 0
        for start in range(0, len(valid_rows), chunk_size):
            end = min(start + chunk_size, len(valid_rows))
            similarities = matrix[start:end] @ matrix.transpose(0, 1)
            for local_index, target in enumerate(valid_rows[start:end]):
                if target["label"] not in DYNAMIC_LABELS:
                    continue
                dynamic_total += 1
                valid_candidate = torch.tensor(
                    [
                        candidate["patient_id"] != target["patient_id"]
                        and candidate["label"] != target["label"]
                        for candidate in valid_rows
                    ],
                    dtype=torch.bool,
                )
                scores = similarities[local_index].masked_fill(
                    ~valid_candidate, float("-inf")
                )
                candidate_index = int(scores.argmax().item())
                best_score = float(scores[candidate_index].item())
                if not torch.isfinite(scores[candidate_index]):
                    continue
                candidate = valid_rows[candidate_index]
                matches.append(
                    {
                        "target_example_id": target["example_id"],
                        "target_pair_id": target["pair_id"],
                        "target_patient_id": target["patient_id"],
                        "partition": target["partition"],
                        "finding": target["finding"],
                        "target_label": target["label"],
                        "target_current_dicom_id": target["current_dicom_id"],
                        "target_current_view": target["current_view"],
                        "counterfactual_example_id": candidate["example_id"],
                        "counterfactual_pair_id": candidate["pair_id"],
                        "counterfactual_patient_id": candidate["patient_id"],
                        "counterfactual_label": candidate["label"],
                        "counterfactual_prior_dicom_id": candidate[
                            "prior_dicom_id"
                        ],
                        "counterfactual_current_dicom_id": candidate[
                            "current_dicom_id"
                        ],
                        "current_cosine_similarity": best_score,
                    }
                )
                group_matched += 1
        group_diagnostics["|".join(key)] = {
            "examples": len(valid_rows),
            "dynamic_examples": group_dynamic,
            "matched_dynamic_examples": group_matched,
        }

    matches.sort(key=lambda item: item["target_example_id"])
    coverage = len(matches) / dynamic_total if dynamic_total else 0.0
    audit = {
        "dynamic_examples": dynamic_total,
        "matched_dynamic_examples": len(matches),
        "coverage": coverage,
        "missing_embedding_count": len(missing_embeddings),
        "missing_embedding_dicom_ids": sorted(missing_embeddings),
        "groups": group_diagnostics,
    }
    return matches, audit
