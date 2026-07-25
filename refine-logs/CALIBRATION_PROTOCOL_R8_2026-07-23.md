# CAPES-CI QPTM R8 Corrective Synthetic Engineering Protocol Frozen

Status: `FROZEN_BEFORE_R8_DRY_RUN`  
Date: 2026-07-23  
Protocol ID: `CAPES_CI_QPTM_R8_2026_07_23`  
Evidence class: `E1_SYNTHETIC_ENGINEERING_NONCONFIRMATORY`

## 1. Authority, inheritance, and frozen boundary

This document is the sole **frozen** authority for R8 and authorizes only the
registered R8 dry-run. The frozen R7 protocol remains immutable evidence and is
the complete base registry from which the effective R8 registry was composed.

Immutable base dependency:

- path: `refine-logs/CALIBRATION_PROTOCOL_R7_2026-07-22.md`;
- SHA-256: `1988fde0de8c38a701562fa2049070838fb33853b972ce779584e06a7ce28ff6`;
- frozen R7 registry SHA-256:
  `eef6738c4bbb25de5eb057fec64d346fe8ffe6e40afdfd63a306f4b717a28783`.

The first JSON object below is the complete, materialized effective R8 registry.
It was derived from the immutable R7 registry under the pinned hash above, but a
runtime loader must read the R8 object directly and must not implement recursive
base-registry merging. Every unlisted R7 scientific value is expanded in the R8
object and inherited exactly.

## 2. Registered R7 evidence and reason for R8

The R7 dry-run is valid engineering evidence:

- summary:
  `artifacts/calibration/capes_ci_qptm_r7_dryrun_20260722_v1/summary.json`;
- summary SHA-256:
  `09c48c11c3a3e00c3671070d7e7eda57c3b58da68382d3277884a65038057e67`;
- post-run audit:
  `artifacts/calibration/capes_ci_qptm_r7_dryrun_20260722_v1/postrun_audit.json`;
- audit file SHA-256:
  `d5f33c680471bd832b83106d76ba98a5431ff4b8ceabc96cbf1cfce82098e25a`;
- audit self-hash:
  `c55a95912f3150ecff8121a70ec23310799d8ba0833c065497f35b34bbd67521`;
- audit verdict: `PASS_R7_DRY_RUN_POSTRUN_AUDIT`.

The first R7 seed-17 smoke is immutable and ineligible:

- failure:
  `artifacts/calibration/capes_ci_qptm_r7_smoke_seed17_20260722_v1/failure.json`;
- failure file SHA-256:
  `24462e5ece275ab532ac81fcd3235bece5224976056fe380c01353ab8ec8986f`;
- status: `TECHNICAL_FAILURE_R7_UNHANDLED_EXCEPTION`;
- stage: `gate_execution`;
- exception type: `RuntimeError`;
- successful summary: absent;
- formal split access: forbidden and not authorized;
- scientific eligibility: false.

The smoke exposed exactly two corrective implementation defects:

1. query NLL was produced through Torch float32 log arithmetic while the
   independent validator recomputed it from persisted JSON probability rows
   using Python `math.log`;
2. the initialization evidence's raw-parameter hash domain was compared with a
   separately encoded runtime `state_dict` hash domain instead of independently
   recomputing the latter under its own registered encoding.

Neither defect changes a model output, method, threshold, seed, split, gate, or
claim boundary. R7 remains immutable and must not be overwritten or
retrospectively accepted as a successful smoke.

## 3. Machine-readable frozen corrective registry

The following complete JSON object is normative and frozen. Its implementation
observation and non-self-referential `freeze_record` bind the governed source
projection. The `freeze_record` is excluded from the canonical registry
projection; final protocol and full-manifest hashes remain external evidence.

```json
{
  "protocol_id": "CAPES_CI_QPTM_R8_2026_07_23",
  "authority_state": "FROZEN_BEFORE_R8_DRY_RUN",
  "evidence_class": "E1_SYNTHETIC_ENGINEERING_NONCONFIRMATORY",
  "base_dependency": {
    "path": "refine-logs/CALIBRATION_PROTOCOL_R7_2026-07-22.md",
    "sha256": "1988fde0de8c38a701562fa2049070838fb33853b972ce779584e06a7ce28ff6",
    "relationship": "immutable_r7_registry_inherited_except_explicit_r8_corrective_overrides",
    "registry_sha256": "eef6738c4bbb25de5eb057fec64d346fe8ffe6e40afdfd63a306f4b717a28783"
  },
  "invalidated_artifacts": [
    {
      "status": "INVALID_DRY_RUN_FALSE_POSITIVE",
      "summary_path": "artifacts/calibration/capes_ci_qptm_r5_dryrun_20260722_v1/summary.json",
      "summary_sha256": "b42054466827306d60995b9dd5a2a412aafdd0e6909e5bbeae02a928826ef4ec",
      "postrun_audit_path": "artifacts/calibration/capes_ci_qptm_r5_dryrun_20260722_v1/postrun_audit.json",
      "postrun_audit_sha256": "5824045e592819632f4bfd077b472a4ffd4196798060e2a1b931e65ce7c61b57",
      "eligible": false
    },
    {
      "status": "INVALID_R6_DRY_RUN_POSTSERIALIZATION_VALIDATION",
      "stored_summary_status": "DRY_RUN_VALIDATED_R6",
      "summary_path": "artifacts/calibration/capes_ci_qptm_r6_dryrun_20260722_v1/summary.json",
      "summary_sha256": "484486ed8c71524292979239fa953704e4a717fdad61c353ceeb58425ffe8bc0",
      "postrun_audit_path": "artifacts/calibration/capes_ci_qptm_r6_dryrun_20260722_v1/postrun_audit.json",
      "postrun_audit_sha256": "5eed0dd7a75473fa126301c6bdf973ac4626794074a1dc8238ed0eaaa40d92c1",
      "postrun_audit_self_sha256": "e466fcdf764df8eecdf888995e1b2bafade18fd9b90c1cddfb45f21e5327df8a",
      "postrun_audit_verdict": "FAIL_STRICT_POSTRUN_SEMANTIC_VALIDATION",
      "invalid_reason": "persisted_summary_failed_strict_postserialization_semantic_validation",
      "eligible": false
    },
    {
      "status": "INVALID_R7_SMOKE_TECHNICAL_CONTRACT_FAILURE",
      "stored_failure_status": "TECHNICAL_FAILURE_R7_UNHANDLED_EXCEPTION",
      "failure_path": "artifacts/calibration/capes_ci_qptm_r7_smoke_seed17_20260722_v1/failure.json",
      "failure_sha256": "24462e5ece275ab532ac81fcd3235bece5224976056fe380c01353ab8ec8986f",
      "stage": "gate_execution",
      "exception_type": "RuntimeError",
      "invalid_reason": "query_nll_arithmetic_domain_and_initialization_runtime_state_hash_domain_mismatch",
      "eligible": false
    }
  ],
  "schema_versions": {
    "resolver": "r8_resolver_v1",
    "summary": "r8_summary_v1",
    "runtime_environment": "r6_runtime_environment_v1",
    "source_manifest": "r7_closed_source_manifest_v1",
    "result": "r6.result.v1",
    "initialization": "r8_initialization_evidence_v1",
    "structural_microcases": "visualvit.r6-structural-audits.v3",
    "counterfactual": "visualvit.r6_counterfactual_audits.v1",
    "independent_validator": "visualvit.r6-validation.v3",
    "data_access_ledger": "r6_split_access_ledger_v1",
    "exact64_ledger": "r6_exact64_call_ledger_v1",
    "reproduction": "r8_reproduction_certificate_v1",
    "failure": "r8_atomic_failure_v1",
    "freeze_record": "r8_freeze_record_v1"
  },
  "output_root_contract": {
    "workspace_relative_parent": "artifacts/calibration",
    "must_not_exist_at_cli_entry": true,
    "must_be_inside_resolved_workspace": true,
    "symlink_or_junction_escape_forbidden": true,
    "phase_leaf_names": {
      "dry_run": "capes_ci_qptm_r8_dryrun_20260723_v1",
      "smoke": "capes_ci_qptm_r8_smoke_seed17_20260723_v1",
      "registered_local": "capes_ci_qptm_r8_registered_local_20260723_v1",
      "registered_slurm4161": "capes_ci_qptm_r8_registered_slurm4161_20260723_v1",
      "reproduction_local": "capes_ci_qptm_r8_reproduction_local_20260723_v1",
      "reproduction_slurm4161": "capes_ci_qptm_r8_reproduction_slurm4161_20260723_v1"
    },
    "reproduction_child_leaf_names": [
      "process_a",
      "process_b"
    ],
    "overwrite_policy": "refuse_before_any_artifact_write"
  },
  "status_vocabulary": {
    "protocol_candidate": "PRE_FREEZE_AWAITING_IMPLEMENTATION_HASHES",
    "protocol_frozen": "FROZEN_BEFORE_R8_DRY_RUN",
    "invalid_ancestor": "INVALID_R6_DRY_RUN_POSTSERIALIZATION_VALIDATION",
    "dry_run_success": "DRY_RUN_VALIDATED_R8",
    "smoke_success": "SMOKE_COMPLETE_R8_NON_GATING",
    "primary_pending_reproduction": "PASS_R8_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
    "final_success": "PASS_R8_SYNTHETIC_ENGINEERING",
    "scientific_stop_prefix": "STOP_R8_",
    "technical_failure": "TECHNICAL_FAILURE_R8_UNHANDLED_EXCEPTION",
    "launcher_failure": "TECHNICAL_FAILURE_R8_REPRODUCTION_LAUNCHER",
    "formal_data": "HOLD",
    "formal_test": "SEALED",
    "invalid_ancestor_smoke": "INVALID_R7_SMOKE_TECHNICAL_CONTRACT_FAILURE"
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
    "expected_runtime_report_sha256": "9d98dc0f5dfa2777c6ccf8b6791f82200fb16a244e7f8e64b408519d6e4f458e",
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
    },
    "expected_ordered_microcase_projection_sha256": "f686344443ffcef3a8263759390d54332503b8d3317379fcd011cf05e2ba9a20",
    "order_contract": {
      "ordered_authority_field": "required_case_ids",
      "microcases_json_object_iteration_order_semantic": false,
      "required_case_ids_exact_registered_order": true,
      "required_case_ids_unique": true,
      "microcase_key_set_equals_required_case_id_set": true,
      "ordered_projection_field": "ordered_microcase_projection_sha256",
      "ordered_projection_preimage": "list_of_objects_case_id_and_evidence_in_required_case_ids_order",
      "ordered_projection_canonicalization": "utf8_json_sort_keys_compact_ascii_no_nan_v1",
      "ordered_projection_recomputed_by_native_and_independent_validators": true
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
      "protocol_frozen": "FROZEN_BEFORE_R8_DRY_RUN",
      "invalid_ancestor": "INVALID_R6_DRY_RUN_POSTSERIALIZATION_VALIDATION",
      "dry_run_success": "DRY_RUN_VALIDATED_R8",
      "smoke_success": "SMOKE_COMPLETE_R8_NON_GATING",
      "primary_pending_reproduction": "PASS_R8_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
      "final_success": "PASS_R8_SYNTHETIC_ENGINEERING",
      "scientific_stop_prefix": "STOP_R8_",
      "technical_failure": "TECHNICAL_FAILURE_R8_UNHANDLED_EXCEPTION",
      "launcher_failure": "TECHNICAL_FAILURE_R8_REPRODUCTION_LAUNCHER",
      "formal_data": "HOLD",
      "formal_test": "SEALED",
      "invalid_ancestor_smoke": "INVALID_R7_SMOKE_TECHNICAL_CONTRACT_FAILURE"
    },
    "schema_versions": {
      "resolver": "r8_resolver_v1",
      "summary": "r8_summary_v1",
      "runtime_environment": "r6_runtime_environment_v1",
      "source_manifest": "r7_closed_source_manifest_v1",
      "result": "r6.result.v1",
      "initialization": "r8_initialization_evidence_v1",
      "structural_microcases": "visualvit.r6-structural-audits.v3",
      "counterfactual": "visualvit.r6_counterfactual_audits.v1",
      "independent_validator": "visualvit.r6-validation.v3",
      "data_access_ledger": "r6_split_access_ledger_v1",
      "exact64_ledger": "r6_exact64_call_ledger_v1",
      "reproduction": "r8_reproduction_certificate_v1",
      "failure": "r8_atomic_failure_v1",
      "freeze_record": "r8_freeze_record_v1"
    },
    "output_root_contract": {
      "phase_leaf_names": {
        "dry_run": "capes_ci_qptm_r8_dryrun_20260723_v1",
        "smoke": "capes_ci_qptm_r8_smoke_seed17_20260723_v1",
        "registered_local": "capes_ci_qptm_r8_registered_local_20260723_v1",
        "registered_slurm4161": "capes_ci_qptm_r8_registered_slurm4161_20260723_v1",
        "reproduction_local": "capes_ci_qptm_r8_reproduction_local_20260723_v1",
        "reproduction_slurm4161": "capes_ci_qptm_r8_reproduction_slurm4161_20260723_v1"
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
      "refine-logs/CALIBRATION_PROTOCOL_R6_2026-07-22.md": "fdc6fbf7e434b665f9b222d51185bddb3b6c5b5c129ab338041abd793d08974a",
      "refine-logs/CALIBRATION_PROTOCOL_R7_2026-07-22.md": "1988fde0de8c38a701562fa2049070838fb33853b972ce779584e06a7ce28ff6",
      "reports/r5_runner_gate_spec_2026-07-22.md": "9ee58dd2053816d216bc5ed8d339fb4bb4488c092fccd090cd05bcbccd385715",
      "scripts/run_query_anchor_r4.py": "6c73fd68b933676bc872573a6f7b6f4ba3d19bd9e26a6fc4ec0343474fd53c6b",
      "scripts/run_query_anchor_r4_reproduction.py": "5a1fb3f3f54f9a1911776ca61533b2141c93fc885551956704938e01299f3174",
      "scripts/run_query_anchor_v2.py": "60d04ca50c86598603491000907d3b1a97bd57d2d26532bc89fc1a7265b89e0d",
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
      "src/visualvit/r6_structural_audits.py": "334cc080343a96fb6173abe6cf6059b8b5ad1ac4c15d7c3051dc5609da1cb438",
      "src/visualvit/r6_validation.py": "b62ac0cf0613067fb98ebc5a45bd010a94176d636c98d2c984474fd81f10a103",
      "src/visualvit/schemas.py": "e91fdb17498bbcca72f31b6859398988cb75e9f5c4a908e0b9a34ca08a2e4ed9",
      "src/visualvit/statistics.py": "0d29aa4216870b7272a4fbec39fef4e5a64249cbc8205b1e4336659989dafc74",
      "src/visualvit/tokenizer.py": "defb9aeddeb2225362d890590a984f26d84cd3840acc8105c4444b2ff096506d",
      "tests/test_calibration_r5.py": "28fb9e90921e36c8cfc6795c4de12b2f125800369956cdf9b0f98e483f2feaa6",
      "tests/test_matching.py": "aaa90cdfe1e29c6b5bad8a644f4c1c56970031246226946f891d1139dc3dec5f",
      "tests/test_query_anchor_r4_runner.py": "de1da642a35aa4493052568d61a0c090de2e00c09e9955b3cb65bc53bb216910",
      "tests/test_query_anchor_v2_runner.py": "366c9813c23c5d26fbdbc33e7b710dbd3ab48b62907ac7b5264b6568d5fb9757",
      "tests/test_r6_counterfactual_audits.py": "3b466b02c3fc7c65d9e7029f925249f789dcb4a440354a254778e15d64270ca8",
      "tests/test_r6_reproduction.py": "ca5a835bd2cbce704cba8f8d3012017ef431efda78d15d8cadce7fee2f5f2241",
      "tests/test_r6_runner_boundary.py": "3464fde5766881006093539dd99bf77c15fac127c09305cdc13ad652bd7ffa19",
      "tests/test_r6_structural_audits.py": "525853077ac14c2de4b95074557fa29e4f47b490f1979fd5d4d1b0cb587b71a7",
      "tests/test_r6_validation.py": "c221090d6e282b8e129b8fe739cf1ab2133be7d79a6771c5bc8c7e8d7bfa17d3",
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
  "summary_serialization_contract": {
    "schema_version": "r7_summary_serialization_v1",
    "encoding": "utf-8",
    "ensure_ascii": true,
    "indent": 2,
    "sort_keys": true,
    "allow_nan": false,
    "terminal_newline_utf8_hex": "0a",
    "serialize_exactly_once": true,
    "parse_exact_serialized_bytes_once": true,
    "validate_reparsed_object_before_publication": true,
    "required_validation_entrypoints": [
      "runner_independent_metric_validator",
      "native_structural_validator",
      "native_counterfactual_validator",
      "strict_terminal_summary_validator"
    ],
    "publish_same_validated_bytes_without_reserialization": true,
    "postserialization_failure_publishes_success_summary": false,
    "postserialization_failure_returns_success": false
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
    "schema_errors_are_json_pointer_records": true,
    "json_object_iteration_order_semantic": false,
    "structural_order_encoded_by_required_case_ids_and_ordered_projection": true,
    "postserialized_terminal_summary_validation_required": true
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
    "pre_output_root_failure_parent": "artifacts/calibration/.r8_pre_root_failures",
    "pre_output_root_filename": "<stage>.<process_uuid>.failure.json",
    "required_failure_stages": [
      "argument_resolution",
      "authority_capture",
      "output_root_validation",
      "output_root_creation",
      "gate_execution",
      "summary_postserialization_validation",
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
      "refine-logs/CALIBRATION_PROTOCOL_R7_2026-07-22.md",
      "refine-logs/CALIBRATION_PROTOCOL_R8_2026-07-23.md",
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
      "canonical_registry_sha256",
      "structural_audit_sha256",
      "structural_audit_tests_sha256",
      "summary_roundtrip_tests_sha256"
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
  "freeze_projection_contract": {
    "canonicalization": "utf8_json_sort_keys_compact_ascii_no_nan_v1",
    "registry_projection_excluded_json_pointers": [
      "/freeze_record"
    ],
    "closed_manifest_excluded_paths": [
      "refine-logs/CALIBRATION_PROTOCOL_R8_2026-07-23.md"
    ]
  },
  "freeze_record": {
    "schema_version": "r8_freeze_record_v1",
    "canonicalization": "utf8_json_sort_keys_compact_ascii_no_nan_v1",
    "registry_projection_excluded_json_pointers": [
      "/freeze_record"
    ],
    "closed_manifest_excluded_paths": [
      "refine-logs/CALIBRATION_PROTOCOL_R8_2026-07-23.md"
    ],
    "protocol_candidate_sha256": "206861bfec5194c82f44ccc45cd505b4c265ae451803fba31a45f8e47ac008e0",
    "implementation_observation_sha256": "89dac883359d07b24bb3ec94fce835d91ccb8d52dcfe06e1f66b294c1197809f",
    "runner_sha256": "6c73fd68b933676bc872573a6f7b6f4ba3d19bd9e26a6fc4ec0343474fd53c6b",
    "reproduction_launcher_sha256": "5a1fb3f3f54f9a1911776ca61533b2141c93fc885551956704938e01299f3174",
    "query_anchor_v2_runner_sha256": "60d04ca50c86598603491000907d3b1a97bd57d2d26532bc89fc1a7265b89e0d",
    "calibration_r5_sha256": "4d5f6569ae349c5fd99563f287fa9cc4c375484aa81a8fad149447bee8326537",
    "matching_sha256": "6186fa380093e984430f8170439f447026a52dab9bdf847b2cc1edf2d02b23ec",
    "runner_tests_sha256": "de1da642a35aa4493052568d61a0c090de2e00c09e9955b3cb65bc53bb216910",
    "query_anchor_v2_tests_sha256": "366c9813c23c5d26fbdbc33e7b710dbd3ab48b62907ac7b5264b6568d5fb9757",
    "calibration_tests_sha256": "28fb9e90921e36c8cfc6795c4de12b2f125800369956cdf9b0f98e483f2feaa6",
    "matching_tests_sha256": "aaa90cdfe1e29c6b5bad8a644f4c1c56970031246226946f891d1139dc3dec5f",
    "semantic_validator_sha256": "b62ac0cf0613067fb98ebc5a45bd010a94176d636c98d2c984474fd81f10a103",
    "semantic_validator_tests_sha256": "c221090d6e282b8e129b8fe739cf1ab2133be7d79a6771c5bc8c7e8d7bfa17d3",
    "boundary_tests_sha256": "3464fde5766881006093539dd99bf77c15fac127c09305cdc13ad652bd7ffa19",
    "reproduction_tests_sha256": "ca5a835bd2cbce704cba8f8d3012017ef431efda78d15d8cadce7fee2f5f2241",
    "gate_spec_sha256": "9ee58dd2053816d216bc5ed8d339fb4bb4488c092fccd090cd05bcbccd385715",
    "structural_audit_sha256": "334cc080343a96fb6173abe6cf6059b8b5ad1ac4c15d7c3051dc5609da1cb438",
    "structural_audit_tests_sha256": "525853077ac14c2de4b95074557fa29e4f47b490f1979fd5d4d1b0cb587b71a7",
    "summary_roundtrip_tests_sha256": "3464fde5766881006093539dd99bf77c15fac127c09305cdc13ad652bd7ffa19",
    "closed_manifest_sha256": "2291351ca274a854a4afc1ffb0da21075e8618a1c0137188a80a4161bbb1828c",
    "canonical_registry_sha256": "2efcf7e55b2d8c5fb78cd6a05af0fa4c3fcc25d37345e8e9287da4c802a2ad72"
  },
  "registry_composition": {
    "materialized_effective_registry": true,
    "runtime_loader_reads_this_object_directly": true,
    "runtime_loader_requires_base_registry_merge": false,
    "provenance_base_path": "refine-logs/CALIBRATION_PROTOCOL_R7_2026-07-22.md",
    "provenance_base_sha256": "1988fde0de8c38a701562fa2049070838fb33853b972ce779584e06a7ce28ff6",
    "provenance_base_registry_sha256": "eef6738c4bbb25de5eb057fec64d346fe8ffe6e40afdfd63a306f4b717a28783",
    "unlisted_r7_values_materialized_exactly": true
  },
  "registered_r7_evidence": {
    "dry_run": {
      "summary_path": "artifacts/calibration/capes_ci_qptm_r7_dryrun_20260722_v1/summary.json",
      "summary_sha256": "09c48c11c3a3e00c3671070d7e7eda57c3b58da68382d3277884a65038057e67",
      "postrun_audit_path": "artifacts/calibration/capes_ci_qptm_r7_dryrun_20260722_v1/postrun_audit.json",
      "postrun_audit_sha256": "d5f33c680471bd832b83106d76ba98a5431ff4b8ceabc96cbf1cfce82098e25a",
      "postrun_audit_self_sha256": "c55a95912f3150ecff8121a70ec23310799d8ba0833c065497f35b34bbd67521",
      "postrun_audit_verdict": "PASS_R7_DRY_RUN_POSTRUN_AUDIT",
      "eligible_engineering_evidence": true,
      "scientific_method_evidence": false
    },
    "smoke_seed17": {
      "failure_path": "artifacts/calibration/capes_ci_qptm_r7_smoke_seed17_20260722_v1/failure.json",
      "failure_sha256": "24462e5ece275ab532ac81fcd3235bece5224976056fe380c01353ab8ec8986f",
      "status": "TECHNICAL_FAILURE_R7_UNHANDLED_EXCEPTION",
      "stage": "gate_execution",
      "exception_type": "RuntimeError",
      "summary_present": false,
      "eligible": false,
      "scientific_method_evidence": false
    }
  },
  "corrective_scope": {
    "allowed_changes": [
      "query_nll_canonical_arithmetic",
      "initialization_runtime_state_hash_recomputation"
    ],
    "forbidden_changes": [
      "formal_data",
      "formal_test_access",
      "method",
      "model_architecture",
      "objective",
      "fixtures",
      "splits",
      "thresholds",
      "seeds",
      "optimizer_settings",
      "registered_steps",
      "gate_order",
      "gate_survival_logic",
      "baselines",
      "counterfactuals",
      "exact64_interface",
      "claim_boundary"
    ],
    "single_corrective_batch": true,
    "threshold_relaxation": false,
    "scientific_semantics_changed": false
  },
  "query_nll_canonical_arithmetic_contract": {
    "authority": "persisted_soft_query_probability_rows_and_oracle_current_indices",
    "oracle_mass_rule": "float(soft_query_probability_rows[i][oracle_current_indices[i]])",
    "clamp_floor": 1e-08,
    "per_case_rule": "-math.log(max(oracle_mass, 1e-8))",
    "vector_field": "soft_query_nll_values",
    "aggregate_rule": "math.fsum(soft_query_nll_values)/len(soft_query_nll_values)",
    "aggregate_field": "soft_query_nll",
    "producer_recomputes_from_persisted_row_values": true,
    "native_validator_recomputes_from_persisted_row_values": true,
    "independent_validator_recomputes_from_persisted_row_values": true,
    "torch_log_result_as_metric_authority": false,
    "device_or_dtype_specific_log_result_as_metric_authority": false,
    "existing_numeric_validation_tolerance_inherited": true,
    "empty_vector_forbidden": true,
    "nonfinite_forbidden": true
  },
  "initialization_runtime_state_hash_contract": {
    "raw_initial_state_sha256_domain_retained": true,
    "effective_initial_state_sha256_domain_retained": true,
    "runtime_initial_state_sha256_domain": "canonical_runtime_state_dict_v1",
    "hash_domains_must_not_be_compared_as_equal": [
      "raw_initial_state_sha256_vs_runtime_initial_state_sha256",
      "effective_initial_state_sha256_vs_runtime_initial_state_sha256"
    ],
    "runtime_state_dict_parameter_order": [
      "current_null_utility",
      "prior_null_utility",
      "residual_coefficient",
      "view_weight_logits"
    ],
    "runtime_state_dict_shapes": {
      "current_null_utility": [],
      "prior_null_utility": [],
      "residual_coefficient": [],
      "view_weight_logits": [
        2
      ]
    },
    "runtime_state_dict_dtype": "torch.float32",
    "runtime_state_dict_value_source": "registered_literal_float32_little_endian_values_loaded_into_runtime_parameter_shapes",
    "per_entry_preimage": "parameter_name_utf8_plus_dtype_ascii_plus_python_tuple_shape_ascii_plus_c_contiguous_tensor_bytes",
    "state_preimage": "concatenate_per_entry_preimages_in_lexicographic_parameter_name_order",
    "hash_algorithm": "sha256",
    "producer_records_runtime_initial_state_sha256": true,
    "native_validator_recomputes_runtime_initial_state_sha256": true,
    "independent_validator_recomputes_runtime_initial_state_sha256_without_importing_runner_or_model": true,
    "transport_result_initial_state_sha256_equals_recomputed_runtime_initial_state_sha256": true,
    "local_baseline_result_initial_state_sha256_equals_recomputed_runtime_initial_state_sha256": true,
    "raw_and_effective_registered_expected_hashes_unchanged": true,
    "seed_to_raw_initial_state_hash_map_unchanged": true
  },
  "inherited_scientific_contract": {
    "method_exact_r7": true,
    "data_exact_r7": true,
    "fixtures_exact_r7": true,
    "splits_exact_r7": true,
    "thresholds_exact_r7": true,
    "seeds_exact_r7": true,
    "optimizer_settings_exact_r7": true,
    "gate_order_exact_r7": true,
    "gate_thresholds_exact_r7": true,
    "counterfactuals_exact_r7": true,
    "exact64_interface_exact_r7": true,
    "data_access_contract_exact_r7": true,
    "formal_boundaries_exact_r7": true
  }
}
```

## 4. Exact corrective implementation requirements

For every query row, the producer must first materialize the JSON-stable
probability-row values, then derive the oracle mass, per-case NLL, and aggregate
NLL from those values with the registered Python arithmetic. Persisted
`soft_query_nll_values` and `soft_query_nll` are derived evidence, not an
independent Torch result. Native and runner-independent validation must perform
the same derivation from the persisted rows and indices.

Initialization evidence retains the R7 raw and effective hash domains and all
registered expected values. R8 adds a distinct runtime-initial-state hash domain
whose preimage is the runtime matcher `state_dict`: four lexicographically
ordered entries, with the two view logits encoded as one shape-`(2,)` tensor.
The runtime hash must be independently reconstructed from the registered
float32 literal bytes and parameter shapes. A raw-state hash must never be used
as a substitute for the runtime-state hash.

Negative tests must fail closed for a tampered probability row, oracle index,
per-case NLL, aggregate NLL, runtime tensor shape, runtime parameter grouping,
runtime hash, raw hash, effective hash, or cross-domain hash substitution.

## 5. Freeze and execution gate

R8 is `FROZEN_BEFORE_R8_DRY_RUN`. Focused and full tests, scoped
lint/format/compile checks, three fresh implementation observations, three fresh
Gate-0 processes, exact source-closure agreement, and all required implementation
hashes were required before the non-self-referential freeze record was inserted.
This freeze:

- sets `dry_run_authorized` to true;
- authorizes creation of only the registered R8 dry-run output root;
- does not authorize R8 smoke, registered, reproduction, or Slurm execution;
- stores every required implementation hash only in `freeze_record`;
- excludes `freeze_record` from the canonical registry projection.

The execution order remains dry-run, independent post-run audit, seed-17 smoke,
registered local CPU, independent reproduction, and only then any separately
authorized server stage. Every phase stops at its first failed gate.

## 6. Formal-data HOLD and allocation 4161

R8 remains E1 synthetic engineering only. Dataset/model downloads, real-image
training, clinical claims, formal-test reveal, formal main experiments, and
formal ablations remain `HOLD` or `SEALED`; every formal claim flag is false.

Retained allocation `4161 / tpami / gpu01` must not be cancelled, released, or
terminated as cleanup after success or failure. R8 never authorizes
`scancel 4161`.
