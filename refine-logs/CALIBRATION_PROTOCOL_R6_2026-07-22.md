# CAPES-CI QPTM R6 Preregistered Synthetic Engineering Protocol

Status: `FROZEN_BEFORE_R6_DRY_RUN`  
Date: 2026-07-22  
Protocol ID: `CAPES_CI_QPTM_R6_2026_07_22`  
Evidence class: `E1_SYNTHETIC_ENGINEERING_NONCONFIRMATORY`

## 1. Authority, invalid R5 artifact, and scope

This document is the sole frozen authority for the next QPTM synthetic
engineering cycle. It supersedes R5 as an execution protocol. R5 remains an
immutable base dependency because R6 retains its method, fixtures, estimands,
thresholds, optimizer settings, and gate order unless this document explicitly
strengthens an evidence boundary.

The immutable R5 authority is:

- path: `refine-logs/CALIBRATION_PROTOCOL_R5_2026-07-22.md`;
- SHA-256:
  `015949a51b06c1da6c0c10b881226979b412d4cac460f6b2e5779db6ac7b4491`.

The first R5 dry-run is permanently classified
`INVALID_DRY_RUN_FALSE_POSITIVE`. Its directory must remain unchanged and it
is ineligible for every R5 or R6 gate, aggregate, reproduction, or claim:

- summary path:
  `artifacts/calibration/capes_ci_qptm_r5_dryrun_20260722_v1/summary.json`;
- immutable summary SHA-256:
  `b42054466827306d60995b9dd5a2a412aafdd0e6909e5bbeae02a928826ef4ec`;
- post-run audit path:
  `artifacts/calibration/capes_ci_qptm_r5_dryrun_20260722_v1/postrun_audit.json`;
- immutable post-run audit SHA-256:
  `5824045e592819632f4bfd077b472a4ffd4196798060e2a1b931e65ce7c61b57`.

The false positive occurred because registered train, inner-development, and
development splits were materialized during the structural and fixture gates,
before their gate-specific authorization. A stored `DRY_RUN_VALIDATED_R5`
status does not override the post-run audit. R6 requires lazy, fail-closed split
access and independently recomputes the access prefix.

R6 tests the same narrow proposition as R5: a query-independent, two-sided
partial-transport owner can recover a persistent correspondence plan, after
which query information may gate only the transported relation/change
representation used by a fixed-budget mediator. R6 does not claim novelty for
cosine similarity, Hungarian assignment, Sinkhorn projection, partial
transport, null rejection, or slot allocation. It authorizes no clinical or
real-data claim.

This file was final-frozen before the first R6 dry-run. The machine registry
contains a non-self-referential freeze record binding the implementation,
validator, tests, launcher, nonprotocol manifest projection, and registry
projection. The final protocol, full registry, and full source-manifest hashes
are recorded externally by the first dry-run and its independent post-run audit.

## 2. Machine-readable frozen registry

The following JSON object is normative. It contains no executable defaults.
Every inherited field is resolved by loading the exact R5 base dependency and
applying the explicit R6 overrides below. A missing override, an implementation
default not represented here, or any disagreement is a Gate-0 failure.

```json
{
  "protocol_id": "CAPES_CI_QPTM_R6_2026_07_22",
  "authority_state": "FROZEN_BEFORE_R6_DRY_RUN",
  "evidence_class": "E1_SYNTHETIC_ENGINEERING_NONCONFIRMATORY",
  "base_dependency": {
    "path": "refine-logs/CALIBRATION_PROTOCOL_R5_2026-07-22.md",
    "sha256": "015949a51b06c1da6c0c10b881226979b412d4cac460f6b2e5779db6ac7b4491",
    "relationship": "immutable_values_inherited_except_explicit_r6_overrides"
  },
  "invalidated_artifacts": [
    {
      "status": "INVALID_DRY_RUN_FALSE_POSITIVE",
      "summary_path": "artifacts/calibration/capes_ci_qptm_r5_dryrun_20260722_v1/summary.json",
      "summary_sha256": "b42054466827306d60995b9dd5a2a412aafdd0e6909e5bbeae02a928826ef4ec",
      "postrun_audit_path": "artifacts/calibration/capes_ci_qptm_r5_dryrun_20260722_v1/postrun_audit.json",
      "postrun_audit_sha256": "5824045e592819632f4bfd077b472a4ffd4196798060e2a1b931e65ce7c61b57",
      "eligible": false
    }
  ],
  "schema_versions": {
    "resolver": "r6_resolver_v1",
    "summary": "r6_summary_v1",
    "runtime_environment": "r6_runtime_environment_v1",
    "source_manifest": "r6_closed_source_manifest_v1",
    "result": "r6.result.v1",
    "initialization": "r6_initialization_evidence_v1",
    "structural_microcases": "visualvit.r6-structural-audits.v2",
    "counterfactual": "visualvit.r6_counterfactual_audits.v1",
    "independent_validator": "visualvit.r6-validation.v1",
    "data_access_ledger": "r6_split_access_ledger_v1",
    "exact64_ledger": "r6_exact64_call_ledger_v1",
    "reproduction": "r6_reproduction_certificate_v1",
    "failure": "r6_atomic_failure_v1",
    "freeze_record": "r6_freeze_record_v1"
  },
  "output_root_contract": {
    "workspace_relative_parent": "artifacts/calibration",
    "must_not_exist_at_cli_entry": true,
    "must_be_inside_resolved_workspace": true,
    "symlink_or_junction_escape_forbidden": true,
    "phase_leaf_names": {
      "dry_run": "capes_ci_qptm_r6_dryrun_20260722_v1",
      "smoke": "capes_ci_qptm_r6_smoke_seed17_20260722_v1",
      "registered_local": "capes_ci_qptm_r6_registered_local_20260722_v1",
      "registered_slurm4161": "capes_ci_qptm_r6_registered_slurm4161_20260722_v1",
      "reproduction_local": "capes_ci_qptm_r6_reproduction_local_20260722_v1",
      "reproduction_slurm4161": "capes_ci_qptm_r6_reproduction_slurm4161_20260722_v1"
    },
    "reproduction_child_leaf_names": [
      "process_a",
      "process_b"
    ],
    "overwrite_policy": "refuse_before_any_artifact_write"
  },
  "status_vocabulary": {
    "protocol_candidate": "PRE_FREEZE_AWAITING_IMPLEMENTATION_HASHES",
    "protocol_frozen": "FROZEN_BEFORE_R6_DRY_RUN",
    "invalid_ancestor": "INVALID_DRY_RUN_FALSE_POSITIVE",
    "dry_run_success": "DRY_RUN_VALIDATED_R6",
    "smoke_success": "SMOKE_COMPLETE_R6_NON_GATING",
    "primary_pending_reproduction": "PASS_R6_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
    "final_success": "PASS_R6_SYNTHETIC_ENGINEERING",
    "scientific_stop_prefix": "STOP_R6_",
    "technical_failure": "TECHNICAL_FAILURE_R6_UNHANDLED_EXCEPTION",
    "launcher_failure": "TECHNICAL_FAILURE_R6_REPRODUCTION_LAUNCHER",
    "formal_data": "HOLD",
    "formal_test": "SEALED"
  },
  "gate_order": [
    "resolution_freeze",
    "structural_input",
    "fixture_identifiability",
    "transport_competence",
    "anti_equivalence",
    "mediator_recovery",
    "fair_baseline",
    "exact64_bridge",
    "independent_reproduction"
  ],
  "run_modes": {
    "dry_run": {
      "trains_models": false,
      "method_pass_forbidden": true
    },
    "smoke": {
      "seeds": [
        17
      ],
      "steps": 1,
      "method_pass_forbidden": true
    },
    "registered": {
      "seeds": [
        17,
        29,
        43
      ],
      "steps": 500,
      "device": "cpu"
    }
  },
  "runtime_contract": {
    "pythonhashseed": "0",
    "omp_num_threads": "1",
    "mkl_num_threads": "1",
    "torch_num_threads": 1,
    "torch_num_interop_threads": 1,
    "deterministic_algorithms_enabled": true,
    "deterministic_debug_mode": "error",
    "cudnn_benchmark": false,
    "cudnn_deterministic": true,
    "locale_rule": "record_language_encoding_decimal_separator_and_preferred_encoding_then_require_exact_replica_equality",
    "timezone_rule": "record_iana_or_windows_zone_name_and_numeric_utc_offset_then_require_all_evidence_timestamps_in_utc_z",
    "secret_safe_environment_allowlist": [
      "PYTHONHASHSEED",
      "OMP_NUM_THREADS",
      "MKL_NUM_THREADS",
      "SLURM_JOB_ID",
      "SLURM_JOB_NAME",
      "SLURMD_NODENAME",
      "CUDA_VISIBLE_DEVICES"
    ],
    "full_environment_dump_forbidden": true
  },
  "resolver_contract": {
    "registry_is_authority": true,
    "implementation_constants_are_observations": true,
    "compare_exact_keys_types_values": true,
    "compare_callable_signatures": true,
    "compare_implementation_source_hashes": true,
    "compare_runtime_reconstructed_config": true,
    "reject_bool_as_integer": true,
    "reject_numeric_strings": true,
    "reject_nonfinite_recursively": true,
    "reject_unknown_or_missing_keys": true,
    "reject_unresolved_markers_recursively": true,
    "no_split_or_model_access": true,
    "fail_before_output_root_creation_on_mismatch": true
  },
  "initialization_evidence_contract": {
    "parameter_order": [
      "residual_coefficient",
      "view_weight_logits.0",
      "view_weight_logits.1",
      "prior_null_utility_raw",
      "current_null_utility_raw"
    ],
    "raw_value_name_suffix": "_raw",
    "effective_value_name_suffix": "_effective",
    "per_parameter_hash_name_suffix": "_tensor_sha256",
    "full_raw_state_hash_field": "raw_initial_state_sha256",
    "full_effective_state_hash_field": "effective_initial_state_sha256",
    "seed_map_hash_field": "seed_to_initial_state_sha256_map_sha256",
    "raw_formulas": "inherit_exact_r5_literal_values_and_parameter_order",
    "effective_formulas": {
      "view_weights_effective": "softmax(view_weight_logits)",
      "residual_coefficient_effective": "0.02*tanh(residual_coefficient_raw)",
      "prior_null_utility_effective": "0.10*tanh(prior_null_utility_raw)",
      "current_null_utility_effective": "0.10*tanh(current_null_utility_raw)"
    },
    "hash_encoding": "canonical_parameter_name_utf8_nul_shape_int64_le_dtype_utf8_nul_tensor_c_contiguous_le_bytes",
    "expected_seed_evidence": {
      "17": {
        "per_parameter_tensor_sha256": {
          "residual_coefficient": "5d42dbe7664d806062c5a50478eca15a66e731388658bb49c076345ea6d18c22",
          "view_weight_logits.0": "4e00407007a31750da65088241bc7e1905369daeb3573b7483f17de932716621",
          "view_weight_logits.1": "084005b1a081965646a3dd9beb8652c4eb49da4c77905049af573dc0e443592e",
          "prior_null_utility_raw": "5d4f9886c3d2d574709971aa0813a679679912849dd38121b498769d8f8283bc",
          "current_null_utility_raw": "3ac447f39290ed8a519d6b65a4d1239180551c101a937de25b121a02e75e6afb"
        },
        "raw_initial_state_sha256": "1a957b1c94790c69c1687743b695e7bd8780dd53a49e72561bdda9d69e06ab51",
        "effective_initial_state_sha256": "9289c61c801adb68e8b22cdbe4f977e371a1f39bbacf09117c2a506cf64cc8d1"
      },
      "29": {
        "per_parameter_tensor_sha256": {
          "residual_coefficient": "fa34e425f5a2a832e09e65f280df42f8f2547b240a7531a64258a5dbd93d431b",
          "view_weight_logits.0": "76f6c6671d4bd0a9bc979cd0a3b60f8f4975709dead3dfb3ded62cb73bf2c35a",
          "view_weight_logits.1": "0058c1cd8eae9931a02232650ecec0df63b7cbd839e85d1882b79112d93a86ad",
          "prior_null_utility_raw": "1edcc28b7fce1b1e6d10a458a62d83dba172a368462ad021232ff77bed9f48e7",
          "current_null_utility_raw": "b7ce33110065dc5987883456ae63949b01668227863d17d2a3b6541fa1615139"
        },
        "raw_initial_state_sha256": "4e6b94a351497f7e20a150af4a1435f33894b68b9b20e2fd502939d6cef4f68e",
        "effective_initial_state_sha256": "fb4ef19c3630b5ebe332214e8c61c78c253f2646f6e77f6574b2d0016dda1e40"
      },
      "43": {
        "per_parameter_tensor_sha256": {
          "residual_coefficient": "65f6b3671905e143d92dec075621d5d9acba4d37c83da2951cfbed5a7c538435",
          "view_weight_logits.0": "e312bf12d6f66a945c9d3ae688340778537dfe793481955399c4f166141dfd89",
          "view_weight_logits.1": "42dd79b0608cb61175faa88578d5d73a576998f85ecae637ff2d3f55fa933b95",
          "prior_null_utility_raw": "c985ed590951c5254a7f6e8d56aeec80c7ec178681dfdfcf36286fbac8f21cce",
          "current_null_utility_raw": "613214091fc567b87b2cbe2eb84dc7410003941845b715aa52daa4faeb31b94b"
        },
        "raw_initial_state_sha256": "382b434037e9c21481321d779e1d30d5f54afb7d2735d4104036e7e4f0581dde",
        "effective_initial_state_sha256": "369f64b37439e5fe31401940cd4e772b300ca217d785bf4a0b51ad1502baa653"
      }
    },
    "seed_to_initial_state_sha256_map_sha256": "8e14c6fba963a42e8264d2d91a29ec9c97741aa1b3ac3a1978657adbbb4aac85",
    "same_seed_byte_exact": true,
    "seeds_17_29_43_distinct": true,
    "global_rng_independent": true
  },
  "structural_microcase_contract": {
    "required_case_ids": [
      "one_persistent_1x1",
      "one_death_1x0",
      "one_birth_0x1",
      "collision_2x1",
      "crossing_2x2",
      "tied_utility_2x2",
      "mixed_persistent_death_birth_2x2",
      "anatomy_forbidden_edge"
    ],
    "expected_input_sha256_by_case": {
      "one_persistent_1x1": "74ab4ad089ff33f597158ad0ea97334c8016f542f67a18e1e570a1b22cbae681",
      "one_death_1x0": "88db3b76fca0a977a92436403b91278024e441bea74bb71c805788e16133a4e2",
      "one_birth_0x1": "5de3d594bbbdc61fcd50c20ff4ca0dde222657502d883e347afbc44e30db8c4c",
      "collision_2x1": "18a3be30c9b9a40761a324b37b0c3eda0a2b32456cb90e01fee37eb4f1ee810c",
      "crossing_2x2": "d4cfbbb5025736db72d005182ae6a3b6a9ad8085bcea4189832fd9974c047b11",
      "tied_utility_2x2": "b4b35cf30fc22610455e76360d604ad05d48c58e329cefc17d0acf1787f5865e",
      "mixed_persistent_death_birth_2x2": "c0ed2c174f94d238823573369e4a7235c066aee5cfd2954eac8d89f946462e6f",
      "anatomy_forbidden_edge": "3fd2d6ed438276e7371ab7127bd3e8b3ccca494f7c820b8d7428ee155a91b217"
    },
    "expected_input_map_sha256": "48933fd0f2331351dd3a2de9d3fc7c517d007d9088cc553f880e7e2d0efb669a",
    "expected_runtime_report_sha256": "5700631d9b4e23340bc4a439de934f7817bf0775757973a9ed0ae2ffd15fc9b4",
    "required_per_case_evidence": [
      "input_sha256_before",
      "input_sha256_after",
      "utility_sha256",
      "soft_plan_sha256",
      "hard_plan_sha256",
      "feasibility_residuals",
      "expected_plan_exact",
      "completion_counts",
      "gradient_audit"
    ],
    "gradient_audit": {
      "registered_parameter_names_exact": true,
      "finite_loss": true,
      "finite_gradients": true,
      "nonzero_expected_gradient_each_trainable_parameter": true,
      "forbidden_input_or_query_gradient": true,
      "optimizer_owner_exact": true
    },
    "completion_audit": {
      "hard_plan_covers_every_prior_once": true,
      "hard_plan_covers_every_current_once": true,
      "persistent_death_birth_partition_exact": true,
      "soft_augmented_marginals_within_frozen_tolerance": true,
      "no_duplicate_real_current_for_global_matcher": true
    }
  },
  "full_chain_counterfactual_contract": {
    "required_audits": [
      "hidden_id_relabel",
      "independent_endpoint_permutation",
      "query_value_substitution_before_transport",
      "forbidden_state_channel_substitution",
      "b4a_deranged_vs_b4b_oracle"
    ],
    "chain_stages": [
      "sanitized_matcher_input",
      "utility",
      "soft_plan",
      "hard_plan_or_local_weights",
      "relation_candidates",
      "allocation",
      "exact64_tokens",
      "projected_embeddings",
      "frozen_readout_scores",
      "predicted_labels"
    ],
    "input_clone_required": true,
    "source_storage_alias_forbidden": true,
    "nonvacuity_hash_change_required": true,
    "inverse_permutation_before_comparison": true,
    "b4_allowlist": [
      "assignment_mode",
      "assignment_tensor",
      "assignment_sha256",
      "causally_downstream_relation_change_values",
      "assignment_induced_source_order",
      "relation_change_token_values",
      "scores",
      "predictions"
    ],
    "all_non_allowlisted_paths_exact": true,
    "repeat_at_structural_and_exact64_boundaries": true
  },
  "implementation_observation_expected": {
    "constants": {
      "feature_dim": 18,
      "identity_views": [
        [
          2,
          8
        ],
        [
          8,
          14
        ]
      ],
      "residual_cap": 0.02,
      "null_utility_cap": 0.1,
      "sinkhorn_temperature": 0.05,
      "sinkhorn_iterations": 256,
      "feasibility_tolerance": 1e-05,
      "transport_learning_rate": 0.02,
      "mediator_learning_rate": 0.02,
      "gradient_clip_norm": 1.0,
      "registered_steps": 500,
      "trainable_seeds": [
        17,
        29,
        43
      ]
    },
    "callable_signatures": {
      "matcher_constructor": [
        {
          "name": "feature_dim",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": "int"
        },
        {
          "name": "identity_start",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "literal",
            "type": "int",
            "value": 2
          },
          "annotation": "int"
        },
        {
          "name": "identity_views",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "literal",
            "type": "NoneType",
            "value": null
          },
          "annotation": "Sequence[tuple[int, int]] | None"
        },
        {
          "name": "residual_cap",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "literal",
            "type": "float",
            "value": 0.02
          },
          "annotation": "float"
        },
        {
          "name": "null_utility_cap",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "literal",
            "type": "float",
            "value": 0.1
          },
          "annotation": "float"
        },
        {
          "name": "temperature",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "literal",
            "type": "float",
            "value": 0.05
          },
          "annotation": "float"
        },
        {
          "name": "sinkhorn_iterations",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "literal",
            "type": "int",
            "value": 256
          },
          "annotation": "int"
        },
        {
          "name": "feasibility_tolerance",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "literal",
            "type": "float",
            "value": 1e-05
          },
          "annotation": "float"
        },
        {
          "name": "anatomy_constrained",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "literal",
            "type": "bool",
            "value": true
          },
          "annotation": "bool"
        }
      ],
      "compute_utilities": [
        {
          "name": "self",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": null
        },
        {
          "name": "regions",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": "RegionBatch"
        }
      ],
      "soft_plan": [
        {
          "name": "self",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": null
        },
        {
          "name": "regions",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": "RegionBatch"
        }
      ],
      "hard_plan": [
        {
          "name": "self",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": null
        },
        {
          "name": "regions",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": "RegionBatch"
        }
      ],
      "structural_audit": [
        {
          "name": "matcher",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": "InvariantPartialOTMatcher"
        }
      ],
      "counterfactual_audit": [
        {
          "name": "batch",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": "QueryAnchorBatch"
        },
        {
          "name": "hooks",
          "kind": "POSITIONAL_OR_KEYWORD",
          "default": {
            "kind": "empty"
          },
          "annotation": "R6ChainHooks"
        },
        {
          "name": "float_atol",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "literal",
            "type": "float",
            "value": 1e-06
          },
          "annotation": "float"
        },
        {
          "name": "hidden_relabeler",
          "kind": "KEYWORD_ONLY",
          "default": {
            "kind": "typed_object",
            "type": "builtins.function"
          },
          "annotation": "Callable[[QueryAnchorBatch], QueryAnchorBatch]"
        }
      ]
    },
    "runtime_parameter_names_from_ast": [
      "current_null_utility",
      "prior_null_utility",
      "residual_coefficient",
      "view_weight_logits"
    ],
    "cli_actions": [
      {
        "dest": "run_dir",
        "option_strings": [
          "--run-dir"
        ],
        "default": null,
        "required": true,
        "nargs": null,
        "choices": null,
        "type": "Path"
      },
      {
        "dest": "steps",
        "option_strings": [
          "--steps"
        ],
        "default": 500,
        "required": false,
        "nargs": null,
        "choices": null,
        "type": "int"
      },
      {
        "dest": "seeds",
        "option_strings": [
          "--seeds"
        ],
        "default": [
          17,
          29,
          43
        ],
        "required": false,
        "nargs": "+",
        "choices": null,
        "type": "int"
      },
      {
        "dest": "dry_run",
        "option_strings": [
          "--dry-run"
        ],
        "default": false,
        "required": false,
        "nargs": 0,
        "choices": null,
        "type": null
      },
      {
        "dest": "smoke",
        "option_strings": [
          "--smoke"
        ],
        "default": false,
        "required": false,
        "nargs": 0,
        "choices": null,
        "type": null
      },
      {
        "dest": "device",
        "option_strings": [
          "--device"
        ],
        "default": "cpu",
        "required": false,
        "nargs": null,
        "choices": [
          "cpu"
        ],
        "type": null
      }
    ],
    "cli_mutually_exclusive_groups": [
      [
        "dry_run",
        "smoke"
      ]
    ],
    "status_literals": {
      "protocol_candidate": "PRE_FREEZE_AWAITING_IMPLEMENTATION_HASHES",
      "protocol_frozen": "FROZEN_BEFORE_R6_DRY_RUN",
      "invalid_ancestor": "INVALID_DRY_RUN_FALSE_POSITIVE",
      "dry_run_success": "DRY_RUN_VALIDATED_R6",
      "smoke_success": "SMOKE_COMPLETE_R6_NON_GATING",
      "primary_pending_reproduction": "PASS_R6_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
      "final_success": "PASS_R6_SYNTHETIC_ENGINEERING",
      "scientific_stop_prefix": "STOP_R6_",
      "technical_failure": "TECHNICAL_FAILURE_R6_UNHANDLED_EXCEPTION",
      "launcher_failure": "TECHNICAL_FAILURE_R6_REPRODUCTION_LAUNCHER",
      "formal_data": "HOLD",
      "formal_test": "SEALED"
    },
    "schema_versions": {
      "resolver": "r6_resolver_v1",
      "summary": "r6_summary_v1",
      "runtime_environment": "r6_runtime_environment_v1",
      "source_manifest": "r6_closed_source_manifest_v1",
      "result": "r6.result.v1",
      "initialization": "r6_initialization_evidence_v1",
      "structural_microcases": "visualvit.r6-structural-audits.v2",
      "counterfactual": "visualvit.r6_counterfactual_audits.v1",
      "independent_validator": "visualvit.r6-validation.v1",
      "data_access_ledger": "r6_split_access_ledger_v1",
      "exact64_ledger": "r6_exact64_call_ledger_v1",
      "reproduction": "r6_reproduction_certificate_v1",
      "failure": "r6_atomic_failure_v1",
      "freeze_record": "r6_freeze_record_v1"
    },
    "output_root_contract": {
      "phase_leaf_names": {
        "dry_run": "capes_ci_qptm_r6_dryrun_20260722_v1",
        "smoke": "capes_ci_qptm_r6_smoke_seed17_20260722_v1",
        "registered_local": "capes_ci_qptm_r6_registered_local_20260722_v1",
        "registered_slurm4161": "capes_ci_qptm_r6_registered_slurm4161_20260722_v1",
        "reproduction_local": "capes_ci_qptm_r6_reproduction_local_20260722_v1",
        "reproduction_slurm4161": "capes_ci_qptm_r6_reproduction_slurm4161_20260722_v1"
      },
      "reproduction_child_leaf_names": [
        "process_a",
        "process_b"
      ]
    },
    "data_access_rules": {
      "structural_input": [
        [
          "clean",
          "literal_audit_fixture"
        ],
        [
          "challenge",
          "literal_audit_fixture"
        ]
      ],
      "fixture_identifiability": [
        [
          "clean",
          "frozen_fixture_audit"
        ],
        [
          "challenge",
          "frozen_fixture_audit"
        ]
      ],
      "transport_competence": [
        [
          "clean",
          "train"
        ],
        [
          "challenge",
          "train"
        ],
        [
          "clean",
          "inner_development"
        ],
        [
          "challenge",
          "inner_development"
        ],
        [
          "clean",
          "development"
        ]
      ],
      "anti_equivalence": [
        [
          "challenge",
          "development"
        ]
      ],
      "mediator_recovery": [
        [
          "clean",
          "train"
        ],
        [
          "clean",
          "development"
        ],
        [
          "challenge",
          "train"
        ],
        [
          "challenge",
          "development"
        ]
      ],
      "fair_baseline": [
        [
          "clean",
          "train"
        ],
        [
          "clean",
          "development"
        ],
        [
          "challenge",
          "train"
        ],
        [
          "challenge",
          "development"
        ]
      ]
    },
    "optimizer_contract": {
      "transport_optimizer": "AdamW",
      "transport_parameter_owner": "InvariantPartialOTMatcher.parameters",
      "mediator_optimizer": "AdamW",
      "mediator_parameter_owner": "QueryRelationProjector.parameters",
      "matched_local_optimizer": "AdamW",
      "matched_local_parameter_owner": "InvariantPartialOTMatcher.parameters"
    },
    "initialization_literal_vector_sha256": {
      "17": "f1da44f311610a3f292baa4c8f0ff03ee6b7881d69872b2b3243434694cc7190",
      "29": "2ecdc2bfe052fac2b251985056ec41ac1da6ff4e5b9e5538afc316a9ab2a913a",
      "43": "a924c851240c484f9038325d4a3477a1d4b4686020b54e5a3de1cad2b5c87ba3"
    },
    "source_hashes": {
      "pyproject.toml": "e5d44cb1c8064ba225868a98cb27f3b54bd4b658cc634821e471550d0bb6b4f7",
      "refine-logs/CALIBRATION_PROTOCOL_R5_2026-07-22.md": "015949a51b06c1da6c0c10b881226979b412d4cac460f6b2e5779db6ac7b4491",
      "reports/r5_runner_gate_spec_2026-07-22.md": "9ee58dd2053816d216bc5ed8d339fb4bb4488c092fccd090cd05bcbccd385715",
      "scripts/run_query_anchor_r4.py": "5b43de6464ab04b23e5dd0d9a77da4741561b4779c91a2f6523d263ebd58cccf",
      "scripts/run_query_anchor_r4_reproduction.py": "88a0b7cd3bbd194c965bb6cd9e23d3cd08dbde3018e332e993b43ba4ad1f92a3",
      "scripts/run_query_anchor_v2.py": "e807ec20a3624affd297f811d55253524628b89abd895dbb50aa651970b8fec5",
      "src/visualvit/__init__.py": "8550fdc2431d88d9edabc1e95570ee99a1511a8515a82904359b25f8be00d787",
      "src/visualvit/allocator.py": "e528c20dd290d9af8e0b97f4cfde84d7a6fd897bec485120943b87ff8fc6aaee",
      "src/visualvit/baselines.py": "c8d89ec7d66f569f5dbae42e7fe76a22c3ddc23d9df06e2b0c3757035c981381",
      "src/visualvit/calibration_query.py": "b3bc7bb8332f085efb29f9557e85f216c11a27d322ad4d10423b6255ebc47541",
      "src/visualvit/calibration_r4.py": "f6bf381d1db21a0eb8f943ec23abb8fbb1cef2a83a65863be90fbd912ccf4731",
      "src/visualvit/calibration_r5.py": "4d5f6569ae349c5fd99563f287fa9cc4c375484aa81a8fad149447bee8326537",
      "src/visualvit/data_qualification.py": "3907b2156cd9ca39e116baf5672e036c1aa85985538afcf22295524f8056cb82",
      "src/visualvit/matching.py": "6186fa380093e984430f8170439f447026a52dab9bdf847b2cc1edf2d02b23ec",
      "src/visualvit/projector.py": "5e98df453d98c576110ae527614afcc643cf8b756d611184c51baad6ba4bc5a1",
      "src/visualvit/query_anchor_model.py": "8049b92b9226420f389178ebc3db49bfce45858ad3bb19707a017cd19f1a51c8",
      "src/visualvit/qwen_adapter.py": "74110803a8302a5153b904401c228e945d76a2ae9dd4e031f080799905b0c211",
      "src/visualvit/r6_counterfactual_audits.py": "abc7a72a159559beebf7ea224e39b774b9e16dcbb4de05cc2f85ed9b71b54595",
      "src/visualvit/r6_structural_audits.py": "c3be4132ffaa23a9ac9525358ae915bcfec911d7d920090dc77a3ed458b06fa5",
      "src/visualvit/r6_validation.py": "71a3fda38043a32f163a20944bd777c87eda1ef21cc6eefdf43ccd9c0cb09cab",
      "src/visualvit/schemas.py": "e91fdb17498bbcca72f31b6859398988cb75e9f5c4a908e0b9a34ca08a2e4ed9",
      "src/visualvit/statistics.py": "0d29aa4216870b7272a4fbec39fef4e5a64249cbc8205b1e4336659989dafc74",
      "src/visualvit/tokenizer.py": "defb9aeddeb2225362d890590a984f26d84cd3840acc8105c4444b2ff096506d",
      "tests/test_calibration_r5.py": "28fb9e90921e36c8cfc6795c4de12b2f125800369956cdf9b0f98e483f2feaa6",
      "tests/test_matching.py": "aaa90cdfe1e29c6b5bad8a644f4c1c56970031246226946f891d1139dc3dec5f",
      "tests/test_query_anchor_r4_runner.py": "5210e35c90fff385262dd47024bd079eb593c29acc4d32076ba893931af61938",
      "tests/test_query_anchor_v2_runner.py": "83b743b5623a614ac513fd7fc0871283e9fa77bc61d472bb58878445ca9022f9",
      "tests/test_r6_counterfactual_audits.py": "3b466b02c3fc7c65d9e7029f925249f789dcb4a440354a254778e15d64270ca8",
      "tests/test_r6_reproduction.py": "b24c5a2380f1d3d19c2641c7c33d80b113bfc0454dfdf321937456b490e5570f",
      "tests/test_r6_runner_boundary.py": "d46e7fc6257af0c10bb9d093649f897c5a91f6c787f248d89778c5dd532dd548",
      "tests/test_r6_structural_audits.py": "a66278ba56debddc9ff7d2a2653e3ef78fc6c2578a73f71fbafa7e5cfa6172d0",
      "tests/test_r6_validation.py": "a9ea29792157237e0f8e216bf49021be9f29615f67b2833b2b639bf872a70564",
      "tests/test_soft_matching.py": "26de1dee09a09e42138f8773193c140ddefada44877bb7cd388ef4dc9ef7a05f"
    }
  },
  "command_provenance_contract": {
    "raw_argv_list": true,
    "parsed_argv_exact_schema": true,
    "semantic_argv_canonical_list": true,
    "resolved_executable_absolute_path": true,
    "resolved_runner_absolute_path": true,
    "resolved_workspace_absolute_path": true,
    "resolved_cwd_absolute_path": true,
    "process_uuid_v4": true,
    "pid_positive_integer": true,
    "hostname_nonempty": true,
    "start_utc_format": "YYYY-MM-DDTHH:MM:SS.ffffffZ",
    "end_utc_format": "YYYY-MM-DDTHH:MM:SS.ffffffZ",
    "monotonic_elapsed_seconds_nonnegative": true,
    "output_root_canonical_absolute_path": true,
    "output_root_relative_leaf_exact": true,
    "record_parent_and_slurm_identifiers_when_present": true
  },
  "strict_schema_contract": {
    "validator": "recursive_exact_key_type_value_and_derived_arithmetic",
    "semantic_metric_validator_entrypoint": "visualvit.r6_validation.validate_r6_metric_evidence",
    "semantic_validator_must_not_import_runner_torch_model_or_data": true,
    "exact_key_sets_at_every_object": true,
    "unknown_and_missing_keys_fail": true,
    "semantic_list_order_exact": true,
    "unordered_sets_encoded_as_sorted_lists": true,
    "sha256_lowercase_hex_length": 64,
    "uuid_version": 4,
    "timestamps_require_utc_z": true,
    "all_numbers_finite": true,
    "counts_nonnegative_integer_not_bool": true,
    "confusion_arithmetic_recomputed": true,
    "averages_deltas_thresholds_recomputed": true,
    "hash_maps_and_unique_counts_recomputed": true,
    "gate_prefix_and_data_access_prefix_recomputed": true,
    "status_recomputed_not_trusted": true,
    "stopped_summary_forbids_later_gate_keys": true,
    "success_summary_exact_gates_0_to_7": true,
    "formal_claim_fields_false": true,
    "schema_errors_are_json_pointer_records": true
  },
  "metric_evidence_contract": {
    "readout_label_metrics": "predictions_and_targets_recompute_accuracy_five_label_macro_f1_and_persistent_three_label_macro_f1",
    "binary_null_metrics": "flattened_actual_and_predicted_vectors_recompute_confusion_support_precision_recall_f1_balanced_accuracy_and_non_gating_accuracy",
    "null_exact_case_metrics": "case_count_and_death_birth_joint_exact_counts_recompute_case_rates",
    "transport_assignment_metrics": "endpoint_correct_vector_row_actual_predicted_vectors_and_soft_oracle_values_with_denominator_recompute_base_metrics",
    "transport_query_metrics": "hard_correct_soft_mass_nll_and_brier_vectors_recompute_all_query_metrics",
    "marginal_control_metrics": "train_and_development_predictions_targets_recompute_macro_f1",
    "marginal_competence_metrics": "train_development_deranged_predictions_targets_and_signed_logit_difference_vector_recompute_all_gating_metrics",
    "exact64_phase_metrics": "per_phase_placeholder_counts_pixel_inputs_used_and_model_frozen_observations_recompute_exact64_checks",
    "mediator_gradient_metrics": "matcher_gradient_non_none_and_nonzero_counts_recompute_frozen_matcher_gradient_check",
    "binding_isomorphism": "independently_captured_b4a_and_b4b_batch_sha256_must_equal",
    "matched_local_metrics": "row_actual_predicted_vectors_and_correct_support_counts_recompute_row_top1_accuracy",
    "plan_and_tensor_sha256": "retained_as_leaf_artifact_hashes_and_compared_exactly_across_reproduction"
  },
  "reproduction_contract": {
    "primary_must_be_strictly_eligible": true,
    "fresh_process_count": 2,
    "sequential_order": [
      "replica_a",
      "replica_b"
    ],
    "replica_b_launch_requires_replica_a_exit_zero_and_exact_pending_status_and_strict_eligibility": true,
    "canonical_json": "utf8_rfc8785_style_sorted_keys_no_nan",
    "canonical_path_normalization": "run_root_relative_posix",
    "volatile_exclusion_paths": [
      "/provenance/start_utc",
      "/provenance/end_utc",
      "/provenance/monotonic_elapsed_seconds",
      "/provenance/pid",
      "/provenance/process_uuid",
      "/provenance/output_root_absolute",
      "/provenance/raw_argv"
    ],
    "semantic_argv_retained": true,
    "environment_contract_retained": true,
    "source_config_access_state_metric_hashes_retained": true,
    "exact_canonical_hash_equality": true,
    "two_equally_malformed_payloads_ineligible": true
  },
  "atomic_failure_contract": {
    "main_and_launcher_top_level_transaction": true,
    "temporary_file_same_directory": true,
    "flush_and_fsync_before_replace": true,
    "non_overwrite_publish": true,
    "original_exception_never_masked": true,
    "secondary_capture_or_publication_error_recorded_without_replacing_original": true,
    "failure_artifact_name": "failure.json",
    "pre_output_root_failure_parent": "artifacts/calibration/.r6_pre_root_failures",
    "pre_output_root_filename": "<stage>.<process_uuid>.failure.json",
    "required_failure_stages": [
      "argument_resolution",
      "authority_capture",
      "output_root_validation",
      "output_root_creation",
      "gate_execution",
      "summary_write",
      "child_launch",
      "child_communicate",
      "stdout_write",
      "stderr_write",
      "child_summary_read",
      "child_summary_parse",
      "child_eligibility",
      "canonical_compare",
      "certificate_write"
    ],
    "child_raw_failure_hash_preserved": true,
    "technical_failure_never_relabelled_scientific_stop": true,
    "zero_exit_only_final_success": true
  },
  "closed_source_allowlist_contract": {
    "mode": "exact_paths_no_recursive_discovery",
    "paths": [
      "pyproject.toml",
      "refine-logs/CALIBRATION_PROTOCOL_R5_2026-07-22.md",
      "refine-logs/CALIBRATION_PROTOCOL_R6_2026-07-22.md",
      "reports/r5_runner_gate_spec_2026-07-22.md",
      "scripts/run_query_anchor_r4.py",
      "scripts/run_query_anchor_r4_reproduction.py",
      "scripts/run_query_anchor_v2.py",
      "src/visualvit/__init__.py",
      "src/visualvit/allocator.py",
      "src/visualvit/baselines.py",
      "src/visualvit/calibration_query.py",
      "src/visualvit/calibration_r4.py",
      "src/visualvit/calibration_r5.py",
      "src/visualvit/data_qualification.py",
      "src/visualvit/matching.py",
      "src/visualvit/projector.py",
      "src/visualvit/query_anchor_model.py",
      "src/visualvit/qwen_adapter.py",
      "src/visualvit/r6_counterfactual_audits.py",
      "src/visualvit/r6_structural_audits.py",
      "src/visualvit/r6_validation.py",
      "src/visualvit/schemas.py",
      "src/visualvit/statistics.py",
      "src/visualvit/tokenizer.py",
      "tests/test_calibration_r5.py",
      "tests/test_matching.py",
      "tests/test_query_anchor_r4_runner.py",
      "tests/test_query_anchor_v2_runner.py",
      "tests/test_r6_counterfactual_audits.py",
      "tests/test_r6_reproduction.py",
      "tests/test_r6_runner_boundary.py",
      "tests/test_r6_structural_audits.py",
      "tests/test_r6_validation.py",
      "tests/test_soft_matching.py"
    ],
    "each_path_required_regular_file": true,
    "symlink_forbidden": true,
    "extra_imported_workspace_module_fails": true,
    "missing_or_extra_manifest_path_fails": true,
    "hash_algorithm": "sha256",
    "manifest_order": "lexicographic_posix_relative_path"
  },
  "data_access_contract": {
    "resolution_freeze": [],
    "structural_input": [
      [
        "clean",
        "literal_audit_fixture"
      ],
      [
        "challenge",
        "literal_audit_fixture"
      ]
    ],
    "fixture_identifiability": [
      [
        "clean",
        "frozen_fixture_audit"
      ],
      [
        "challenge",
        "frozen_fixture_audit"
      ]
    ],
    "transport_competence": [
      [
        "clean",
        "train"
      ],
      [
        "challenge",
        "train"
      ],
      [
        "clean",
        "inner_development"
      ],
      [
        "challenge",
        "inner_development"
      ],
      [
        "clean",
        "development"
      ]
    ],
    "anti_equivalence": [
      [
        "challenge",
        "development"
      ]
    ],
    "mediator_recovery": [
      [
        "clean",
        "train"
      ],
      [
        "clean",
        "development"
      ],
      [
        "challenge",
        "train"
      ],
      [
        "challenge",
        "development"
      ]
    ],
    "fair_baseline": [
      [
        "clean",
        "train"
      ],
      [
        "clean",
        "development"
      ],
      [
        "challenge",
        "train"
      ],
      [
        "challenge",
        "development"
      ]
    ],
    "exact64_bridge": [],
    "independent_reproduction": [],
    "gate_7_reads_cached_snapshots_only": true,
    "gate_8_reads_child_artifacts_only": true
  },
  "freeze_requirements": {
    "implementation_hashes_frozen": true,
    "required_hash_fields": [
      "protocol_candidate_sha256",
      "implementation_observation_sha256",
      "runner_sha256",
      "reproduction_launcher_sha256",
      "query_anchor_v2_runner_sha256",
      "calibration_r5_sha256",
      "matching_sha256",
      "runner_tests_sha256",
      "query_anchor_v2_tests_sha256",
      "calibration_tests_sha256",
      "matching_tests_sha256",
      "semantic_validator_sha256",
      "semantic_validator_tests_sha256",
      "boundary_tests_sha256",
      "reproduction_tests_sha256",
      "gate_spec_sha256",
      "closed_manifest_sha256",
      "canonical_registry_sha256"
    ],
    "dry_run_authorized": true
  },
  "formal_boundaries": {
    "formal_test": "SEALED",
    "formal_data": "HOLD",
    "formal_claim_flags": false,
    "real_data_or_model_download_authorized": false,
    "allocation_4161_release_authorized": false
  },
  "freeze_record": {
    "schema_version": "r6_freeze_record_v1",
    "canonicalization": "utf8_json_sort_keys_compact_ascii_no_nan_v1",
    "registry_projection_excluded_json_pointers": [
      "/freeze_record"
    ],
    "closed_manifest_excluded_paths": [
      "refine-logs/CALIBRATION_PROTOCOL_R6_2026-07-22.md"
    ],
    "protocol_candidate_sha256": "bea370c6edf27a64aaea725da99e3ebaf12ed2df8756017b7589f745c0035c49",
    "implementation_observation_sha256": "c75c6040df3e50f848db0b8140d6f929963193e309ff32a3b89df48d89132058",
    "runner_sha256": "5b43de6464ab04b23e5dd0d9a77da4741561b4779c91a2f6523d263ebd58cccf",
    "reproduction_launcher_sha256": "88a0b7cd3bbd194c965bb6cd9e23d3cd08dbde3018e332e993b43ba4ad1f92a3",
    "query_anchor_v2_runner_sha256": "e807ec20a3624affd297f811d55253524628b89abd895dbb50aa651970b8fec5",
    "calibration_r5_sha256": "4d5f6569ae349c5fd99563f287fa9cc4c375484aa81a8fad149447bee8326537",
    "matching_sha256": "6186fa380093e984430f8170439f447026a52dab9bdf847b2cc1edf2d02b23ec",
    "runner_tests_sha256": "5210e35c90fff385262dd47024bd079eb593c29acc4d32076ba893931af61938",
    "query_anchor_v2_tests_sha256": "83b743b5623a614ac513fd7fc0871283e9fa77bc61d472bb58878445ca9022f9",
    "calibration_tests_sha256": "28fb9e90921e36c8cfc6795c4de12b2f125800369956cdf9b0f98e483f2feaa6",
    "matching_tests_sha256": "aaa90cdfe1e29c6b5bad8a644f4c1c56970031246226946f891d1139dc3dec5f",
    "semantic_validator_sha256": "71a3fda38043a32f163a20944bd777c87eda1ef21cc6eefdf43ccd9c0cb09cab",
    "semantic_validator_tests_sha256": "a9ea29792157237e0f8e216bf49021be9f29615f67b2833b2b639bf872a70564",
    "boundary_tests_sha256": "d46e7fc6257af0c10bb9d093649f897c5a91f6c787f248d89778c5dd532dd548",
    "reproduction_tests_sha256": "b24c5a2380f1d3d19c2641c7c33d80b113bfc0454dfdf321937456b490e5570f",
    "gate_spec_sha256": "9ee58dd2053816d216bc5ed8d339fb4bb4488c092fccd090cd05bcbccd385715",
    "closed_manifest_sha256": "d7901f93f71e6752bedf6380bce91153203962ac4cdbe7c7a08e67705a745637",
    "canonical_registry_sha256": "cfd0db0cf5853dfe465ab093d24a68fdce53a7a3d235eb0d2ea8c312e19c2bd9"
  }
}
```

## 3. Resolver: registry authority versus implementation observation

Gate 0 must load the exact machine JSON above and the exact R5 dependency. It
must construct a second object from implementation observations without
copying registry values into that object. The implementation observation must
include callable signatures, constants, source hashes, parameter names,
registered initialization literals, optimizer settings, thresholds, split
seeds, access rules, schema versions, status strings, and output-root leaves.
The two objects are compared recursively by exact key, type, and value.

The registry is authoritative; code constants are never treated as evidence
that the registry agrees with itself. A field absent from either side fails.
An implementation default used by a call but absent from the registry fails.
An unknown implementation key fails. The resolver must also reparse this
document's JSON independently and compare its canonical hash with the frozen
registry hash after final freeze.

Gate 0 has no split provider, fixture, model, optimizer, or output writer in its
signature. It validates the CLI and non-existing output root read-only. It may
create no run directory until every resolution check passes. Any split
generator call, source-manifest discovery outside the closed allowlist, or
model construction during Gate 0 is a technical failure.

## 4. Runtime determinism and environment evidence

Before model construction the runner must set PyTorch intra-op and inter-op
threads to one, enable deterministic algorithms, set deterministic debug mode
to `error`, disable cuDNN benchmarking, and enable deterministic cuDNN behavior.
It must then observe and record the resulting values. Merely recording intended
values is insufficient.

Locale evidence includes locale name, preferred encoding, filesystem encoding,
standard-stream encodings, decimal separator, and thousands separator. Timezone
evidence includes the operating-system zone name and numeric UTC offset.
Evidence timestamps are emitted only in UTC with a literal `Z`; naive datetime
strings and local wall-clock strings are invalid. The runtime record includes
Python, PyTorch, NumPy when imported, OS/build, CPU, CUDA availability/build,
thread settings, deterministic settings, and only the environment keys in the
machine allowlist. Values outside that allowlist must not enter an artifact.

The dry-run and replicas must prove the same deterministic contract. Hostname,
PID, process UUID, absolute output root, UTC times, and elapsed time are
provenance, not semantic equality fields, but they remain in raw artifacts.

## 5. Initialization evidence naming and hashing

Each seed record must report every parameter in the exact registered order. A
raw trainable value and its transformed effective value are different fields.
No field named simply `value`, `coefficient`, `null_utility`, or `state_hash` is
permitted because it is ambiguous.

For scalars, records contain `<parameter>_raw`, `<parameter>_effective`, and
`<parameter>_tensor_sha256`. The two view logits additionally report
`view_weight_logits_raw`, `view_weights_effective`, the individual scalar
hashes, and the combined two-element tensor hash. The complete record contains
`raw_initial_state_sha256`, `effective_initial_state_sha256`, and the hash of
the exact seed-to-state map.

The tensor hash preimage includes canonical parameter name, shape, dtype, and
little-endian contiguous bytes, so hashes of identical bytes under different
parameter names are not interchangeable. Gate 3 independently re-derives the
R5 frozen literal values and every raw/effective/hash field. Repeating one seed
must be byte-identical, seeds 17/29/43 must have three distinct complete raw
state hashes, and unrelated global RNG consumption must not alter them.

## 6. Structural microcases, gradients, and completion

Gate 1 runs the eight frozen microcases from the registry before any registered
split is available. Each microcase is generated from literal tensors within the
test authority, and its visible input hash is fixed at final freeze. No
registered train or development tensor may be substituted.

The microcases jointly exercise persistent, death-only, birth-only, collision,
crossing, tied-utility, mixed completion, and forbidden-anatomy behavior. Every
hard plan must satisfy exact two-sided completion: each prior is persistent or
death exactly once; each current is persistent or birth exactly once; anatomy-
forbidden edges are absent; global real columns are not duplicated. Every soft
plan must satisfy the augmented marginal tolerance inherited from R5.

The gradient micro-audit performs one registered loss backward pass without an
optimizer step. It records loss, every parameter name, gradient presence,
finite status, norm, and hash. All registered trainable parameters must receive
a finite nonzero gradient on the union of the microcases. Query markers,
labels, hidden IDs, state channels, inputs, oracle tensors, and null masks may
not receive gradients. A parameter missing from the optimizer or an unexpected
optimizer-owned parameter fails before training.

## 7. Full-chain counterfactuals

Counterfactual evidence must cover the complete chain, not only the matcher.
For every required audit the runner snapshots sanitized matcher inputs,
utilities, plans or local weights, relation candidates, allocation, exact-64
tokens and metadata, projected embeddings, frozen-readout scores, and labels.
The transformed fixture is storage-disjoint from its source and the source
snapshot is bitwise unchanged after each stage.

Hidden-ID relabel and query/state substitutions must leave transport and every
pre-query transported representation exact. Endpoint permutations must be
independent on the two sides, non-identity, and restored by the recorded inverse
before comparison. Floating comparisons use the inherited R5 numerical
tolerance; hard plans, indices, masks, types, positions, and hashes are exact.

B4a and B4b use one bitwise-identical input/model/readout/adapter chain. Only
the registered assignment and its causally downstream fields may differ. A
recursive structural diff must enumerate paths and reject every path outside
the machine allowlist. B4a equal to B4b, an identity relabel, or an identity
permutation is vacuous and fails. All counterfactuals run once at Gate 1 and
again through the exact-64 adapter at Gate 7.

## 8. Commands, UTC provenance, and output-root safety

The runner records raw argv as a list, parsed arguments under an exact schema,
and a normalized semantic argv. Shell command strings are diagnostic only and
cannot replace argv lists. Executable, runner, workspace, cwd, and output root
are canonical absolute paths. The output root must resolve beneath the current
workspace's `artifacts/calibration` directory and end in the exact phase leaf
from the registry. Junction, symlink, `..`, case-fold, or alternate-drive
escape fails.

At CLI entry the output root must not exist. Validation occurs before creating
it. Creation is exclusive; any race or collision fails without overwrite.
Dry-run, smoke, primary, Slurm primary, and reproduction roots are distinct.
Every summary contains UTC start/end timestamps, monotonic elapsed time, PID,
UUID, hostname, parent identity when present, and Slurm identifiers when
present. A command/output-root mismatch is a resolution failure rather than a
warning.

## 9. Lazy access and stop-first-fail

R6 retains the R5 gate order but corrects its implementation. Gate 0 reads no
data. Gate 1 uses only literal structural microfixtures. Gate 2 uses only frozen
fixture-audit data. Gate 3 may access transport train, then inner-development
after final-step training, then clean development after checkpoint freeze.
Gate 4 may access challenge development only after Gate 3 passes. Gate 5 may
access mediator train and authorized development only after matcher/readout
freeze. Gate 6 may access baseline train and common-readout development after
all baseline checkpoints freeze. Gate 7 reads immutable cached Gate-6
snapshots and accesses no new split. Gate 8 reads child artifacts only.

One accessor appends gate, stratum, split, purpose, content hash, and cache-hit
status before returning a batch. An unauthorized request raises a technical
error. Every stop contains exactly the completed gate and accessed-data prefix;
later keys, caches, hashes, and metrics are forbidden. The resolver and strict
schema validator independently recompute this prefix.

## 10. Strict recursive schema and canonical reproduction

Every registered object has an exact schema version and exact key set. The
validator rejects unknown/missing keys, booleans as integers, numeric strings,
non-finite values at any depth, malformed hashes, invalid UUIDs, naive or
non-UTC timestamps, wrong seed/method/split sets, reordered semantic lists,
inconsistent confusion counts, forged averages/deltas, invalid access prefixes,
and stored gate booleans inconsistent with recomputation. Errors are JSON
Pointer records containing expected rule and observed value/type.

A successful primary contains Gates 0-7 exactly and the pending-reproduction
status. A stopped result contains one first failing gate and no later-stage
fields. Canonical equality never repairs schema ineligibility.

The reproduction launcher validates the primary before starting replica A.
Replica B starts only after replica A exits zero, reports the exact pending
status, and passes strict validation. Both replicas are fresh sequential
processes with distinct PIDs and UUIDs. Raw artifacts preserve command, paths,
timestamps, PIDs, UUIDs, logs, and failures. Canonical comparison removes only
the exact volatile JSON Pointer paths in the registry, normalizes run-root paths
to relative POSIX paths, retains semantic argv and all scientific/runtime
authority evidence, and requires exact canonical hashes.

## 11. Atomic failure evidence

The main runner and reproduction launcher each use one fail-closed top-level
transaction. Before the requested output root exists, failures are published
under `artifacts/calibration/.r6_pre_root_failures/` with a unique
`<stage>.<process_uuid>.failure.json` leaf; this never creates the requested run
root. After output-root creation, every registered failure stage best-effort
writes a same-directory temporary JSON file, flushes and fsyncs it where
supported, then publishes `failure.json` without overwriting an existing
artifact. Failure publication errors are attached to stderr while the original
exception and traceback remain primary.

Failure evidence includes protocol/schema version, stage, exception type,
message and traceback, UTC times, command/cwd/PID/UUID, output-root validation
state, whitelisted environment, source/config capture or capture error, gate and
access prefix, child command/PID/return code when known, log paths/hashes, and
child summary/failure paths/hashes when present. All formal claim flags are
false. A child technical failure is referenced by raw hash and is never
rewritten as a scientific stop. Zero exit is reserved for the final registered
success appropriate to the invoked mode.

## 12. Closed source allowlist and final-freeze handoff

Source capture uses only the exact relative paths in the machine registry,
sorted lexicographically after POSIX normalization. Recursive directory walks,
glob expansion, implicit import discovery as the manifest authority, symlinks,
and unlisted workspace modules are forbidden. Runtime import observation is a
separate audit: an imported workspace file missing from the allowlist fails.
Every path must be a regular file beneath the resolved workspace. Gate 0 hashes
each file immediately before and immediately after resolution and rejects drift.

Before changing the authority state, the main thread independently verified and
froze the candidate-protocol lineage hash; main, reproduction, and v2 runner
hashes; calibration and matcher hashes; runner, v2, calibration, matcher,
validator, boundary, and reproduction test hashes; the gate-specification hash;
the implementation-observation hash; the nonprotocol closed-manifest projection;
and the final registry projection with `/freeze_record` removed.

The embedded `closed_manifest_sha256` excludes this R6 protocol and excludes
runtime import observations. The embedded `canonical_registry_sha256` excludes
only `/freeze_record`. These are the only embedded projections needed to avoid
self-reference. The final protocol SHA-256, full registry SHA-256, full source
manifest SHA-256, final config SHA-256, dry-run summary SHA-256, and post-run
audit SHA-256 cannot be embedded without self-reference and must be recorded as
external evidence by the first dry-run and its post-run audit.

The final observed protocol hash is recomputed after the last edit. A dry-run
attempted with any failed freeze-record projection, while
`implementation_hashes_frozen` is false, or while `dry_run_authorized` is false
must fail Gate 0 without creating the output root.

Any source, registry, schema, output-root, status-vocabulary, microfixture, or
threshold change after the first valid R6 dry-run supersedes R6 and requires a
new protocol ID and new output roots. Negative, invalid, and technical artifacts
remain immutable and visible.

## 13. Formal-data HOLD and retained allocation 4161

R6 authorizes only E0 analytic/unit checks and E1 synthetic engineering. It
does not authorize dataset/model downloads, real-image training, clinical
claims, or formal-test reveal. Formal data remain `HOLD`; formal test remains
`SEALED`; all formal claim flags remain false.

The CPU-only registered process may run inside retained Slurm allocation 4161
after a valid local dry-run and smoke. Allocation 4161 must not be cancelled,
released, or terminated as cleanup after success, failure, or reproduction.
This protocol never authorizes `scancel 4161`.
