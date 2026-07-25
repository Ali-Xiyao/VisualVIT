# CAPES-CI QPTM R22 Source-Manifest Authority Protocol Frozen

Status: `FROZEN_BEFORE_R22_REPRODUCTION`
Date: 2026-07-23
Protocol ID: `CAPES_CI_QPTM_R22_2026_07_23`
Evidence class: `E1_SYNTHETIC_ENGINEERING_NONCONFIRMATORY`

## 1. Authority, evidence, and frozen boundary

This document is the sole **frozen** authority for R22. It derives
from the exact frozen R21 protocol and complete registry pinned below. Runtime
code must read this first JSON object directly and must not recursively merge
R21. Before one-shot finalization, R22 cannot issue an audit or certificate,
consume a claim, create an output root, access data, execute Gate 0, or support
a method, server, or scientific inference.

## 2. Machine-readable complete frozen registry

```json
{
  "protocol_id": "CAPES_CI_QPTM_R22_2026_07_23",
  "authority_state": "FROZEN_BEFORE_R22_REPRODUCTION",
  "evidence_class": "E1_SYNTHETIC_ENGINEERING_NONCONFIRMATORY",
  "base_dependency": {
    "path": "refine-logs/CALIBRATION_PROTOCOL_R21_2026-07-23.md",
    "protocol_sha256": "693e9e887b9912fa00b532535be95e34abe41b0d15930505a457f8a781b92f1d",
    "registry_sha256": "a3735022a60575477800f0395f83dc7809a11c26a59dd41a36d363939e70f04f",
    "registry_sha256_semantics": "r21_full_canonical_registry_including_complete_freeze_record",
    "authority_state": "FROZEN_BEFORE_R21_REPRODUCTION"
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
    },
    {
      "status": "INELIGIBLE_UNAUTHORIZED_R8_SMOKE_TECHNICAL_FAILURE",
      "stored_failure_status": "TECHNICAL_FAILURE_R8_UNHANDLED_EXCEPTION",
      "failure_path": "artifacts/calibration/capes_ci_qptm_r8_smoke_seed17_20260723_v1/failure.json",
      "failure_sha256": "c9dcac95d20855794e2fc7251c339802b6e378f9bc6009f058ed98992a07d59f",
      "stage": "summary_postserialization_validation",
      "exception_type": "RuntimeError",
      "summary_written": false,
      "launch_authorized_by_frozen_r8_protocol": false,
      "invalid_reason": "r8_smoke_was_not_phase_authorized_and_persisted_summary_validation_exposed_json_object_iteration_order_as_an_incorrect_semantic_dependency",
      "eligible": false
    }
  ],
  "schema_versions": {
    "resolver": "r22_resolver_v1",
    "summary": "r22_summary_v1",
    "runtime_environment": "r6_runtime_environment_v1",
    "source_manifest": "r22_source_manifest_v1",
    "result": "r6.result.v1",
    "initialization": "r22_initialization_evidence_v1",
    "structural_microcases": "visualvit.r6-structural-audits.v3",
    "counterfactual": "visualvit.r6_counterfactual_audits.v1",
    "independent_validator": "visualvit.r6-validation.v4",
    "data_access_ledger": "r6_split_access_ledger_v1",
    "exact64_ledger": "r6_exact64_call_ledger_v1",
    "reproduction": "r22_reproduction_certificate_v1",
    "failure": "r22_atomic_failure_v1",
    "freeze_record": "r22_freeze_record_v1",
    "dryrun_postrun_audit": "r22_dryrun_postrun_audit_v1",
    "smoke_authorization": "r22_smoke_authorization_certificate_v1",
    "smoke_postrun_audit": "r22_smoke_postrun_audit_v1",
    "registered_authorization": "r22_registered_authorization_certificate_v1"
  },
  "output_root_contract": {
    "workspace_relative_parent": "artifacts/calibration",
    "must_not_exist_at_cli_entry": true,
    "must_be_inside_resolved_workspace": true,
    "symlink_or_junction_escape_forbidden": true,
    "phase_leaf_names": {
      "dry_run": "capes_ci_qptm_r22_dryrun_20260723_v1",
      "smoke": "capes_ci_qptm_r22_smoke_seed17_20260723_v1",
      "registered_local": "capes_ci_qptm_r22_registered_local_20260723_v1",
      "registered_slurm4161": "capes_ci_qptm_r22_registered_slurm4161_20260723_v1",
      "reproduction_local": "capes_ci_qptm_r22_reproduction_local_20260723_v1",
      "reproduction_slurm4161": "capes_ci_qptm_r22_reproduction_slurm4161_20260723_v1"
    },
    "reproduction_child_leaf_names": [
      "process_a",
      "process_b"
    ],
    "overwrite_policy": "refuse_before_any_artifact_write"
  },
  "status_vocabulary": {
    "protocol_candidate": "PRE_FREEZE_AWAITING_R22_IMPLEMENTATION_HASHES",
    "protocol_frozen": "FROZEN_BEFORE_R22_REPRODUCTION",
    "invalid_ancestor": "INVALID_R6_DRY_RUN_POSTSERIALIZATION_VALIDATION",
    "invalid_ancestor_smoke": "INELIGIBLE_UNAUTHORIZED_R8_SMOKE_TECHNICAL_FAILURE",
    "dry_run_success": "DRY_RUN_VALIDATED_R22",
    "smoke_authorized": "AUTHORIZED_R22_SMOKE",
    "smoke_success": "SMOKE_COMPLETE_R22_NON_GATING",
    "registered_local_authorized": "AUTHORIZED_R22_REGISTERED_LOCAL",
    "primary_pending_reproduction": "PASS_R14_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
    "final_success": "PASS_R22_SYNTHETIC_ENGINEERING",
    "scientific_stop_prefix": "STOP_R22_",
    "technical_failure": "TECHNICAL_FAILURE_R22_UNHANDLED_EXCEPTION",
    "launcher_failure": "TECHNICAL_FAILURE_R22_REPRODUCTION_LAUNCHER",
    "phase_authorization_failure": "TECHNICAL_FAILURE_R22_PHASE_AUTHORIZATION",
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
      ],
      "exact64_method_order": [
        "main",
        "local_independent",
        "hungarian",
        "sinkhorn"
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
      "protocol_candidate": "PRE_FREEZE_AWAITING_R22_IMPLEMENTATION_HASHES",
      "protocol_frozen": "FROZEN_BEFORE_R22_REPRODUCTION",
      "invalid_ancestor": "INVALID_R6_DRY_RUN_POSTSERIALIZATION_VALIDATION",
      "invalid_ancestor_smoke": "INELIGIBLE_UNAUTHORIZED_R8_SMOKE_TECHNICAL_FAILURE",
      "dry_run_success": "DRY_RUN_VALIDATED_R22",
      "smoke_authorized": "AUTHORIZED_R22_SMOKE",
      "smoke_success": "SMOKE_COMPLETE_R22_NON_GATING",
      "registered_local_authorized": "AUTHORIZED_R22_REGISTERED_LOCAL",
      "primary_pending_reproduction": "PASS_R14_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
      "final_success": "PASS_R22_SYNTHETIC_ENGINEERING",
      "scientific_stop_prefix": "STOP_R22_",
      "technical_failure": "TECHNICAL_FAILURE_R22_UNHANDLED_EXCEPTION",
      "launcher_failure": "TECHNICAL_FAILURE_R22_REPRODUCTION_LAUNCHER",
      "phase_authorization_failure": "TECHNICAL_FAILURE_R22_PHASE_AUTHORIZATION",
      "formal_data": "HOLD",
      "formal_test": "SEALED"
    },
    "schema_versions": {
      "resolver": "r22_resolver_v1",
      "summary": "r22_summary_v1",
      "runtime_environment": "r6_runtime_environment_v1",
      "source_manifest": "r22_source_manifest_v1",
      "result": "r6.result.v1",
      "initialization": "r22_initialization_evidence_v1",
      "structural_microcases": "visualvit.r6-structural-audits.v3",
      "counterfactual": "visualvit.r6_counterfactual_audits.v1",
      "independent_validator": "visualvit.r6-validation.v4",
      "data_access_ledger": "r6_split_access_ledger_v1",
      "exact64_ledger": "r6_exact64_call_ledger_v1",
      "reproduction": "r22_reproduction_certificate_v1",
      "failure": "r22_atomic_failure_v1",
      "freeze_record": "r22_freeze_record_v1",
      "dryrun_postrun_audit": "r22_dryrun_postrun_audit_v1",
      "smoke_authorization": "r22_smoke_authorization_certificate_v1",
      "smoke_postrun_audit": "r22_smoke_postrun_audit_v1",
      "registered_authorization": "r22_registered_authorization_certificate_v1"
    },
    "output_root_contract": {
      "phase_leaf_names": {
        "dry_run": "capes_ci_qptm_r22_dryrun_20260723_v1",
        "smoke": "capes_ci_qptm_r22_smoke_seed17_20260723_v1",
        "registered_local": "capes_ci_qptm_r22_registered_local_20260723_v1",
        "registered_slurm4161": "capes_ci_qptm_r22_registered_slurm4161_20260723_v1",
        "reproduction_local": "capes_ci_qptm_r22_reproduction_local_20260723_v1",
        "reproduction_slurm4161": "capes_ci_qptm_r22_reproduction_slurm4161_20260723_v1"
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
      "refine-logs/CALIBRATION_PROTOCOL_R8_2026-07-23.md": "9f360cc11ed50275482d419629205374bc83febe96f31dc73e93bc45c30f6291",
      "refine-logs/CALIBRATION_PROTOCOL_R9_2026-07-23.md": "c11a9c6677909c8ecab6645cf4d7aa79e3b7470aee573fb7e6c4a857dda00f8b",
      "reports/r5_runner_gate_spec_2026-07-22.md": "9ee58dd2053816d216bc5ed8d339fb4bb4488c092fccd090cd05bcbccd385715",
      "scripts/run_query_anchor_r4.py": "2348f5e181fd5c9351777692c0b3f8cbe36a5178feccd8427547f1c737e0516d",
      "scripts/run_query_anchor_r4_reproduction.py": "f02f17f1f679b8e621ecd5b36dc20d276fff54d9175136edfcb6886ca184ad90",
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
      "src/visualvit/r6_validation.py": "07e179c046373b99c30118c09c821a7f896065b9ca41d354315b6c974ff6f3f8",
      "src/visualvit/schemas.py": "e91fdb17498bbcca72f31b6859398988cb75e9f5c4a908e0b9a34ca08a2e4ed9",
      "src/visualvit/statistics.py": "0d29aa4216870b7272a4fbec39fef4e5a64249cbc8205b1e4336659989dafc74",
      "src/visualvit/tokenizer.py": "defb9aeddeb2225362d890590a984f26d84cd3840acc8105c4444b2ff096506d",
      "tests/test_calibration_r5.py": "28fb9e90921e36c8cfc6795c4de12b2f125800369956cdf9b0f98e483f2feaa6",
      "tests/test_frozen_source_manifest_cross_process.py": "f184d6d28d44fe860a6273b136beb6fbe0397adb5864dfdbdec8e53aa5291c5f",
      "tests/test_matching.py": "aaa90cdfe1e29c6b5bad8a644f4c1c56970031246226946f891d1139dc3dec5f",
      "tests/test_query_anchor_r4_runner.py": "565d147c09cbb60a158b971f7c22b5875e0e863666e51b9aaa00e582db2ed5ad",
      "tests/test_query_anchor_v2_runner.py": "366c9813c23c5d26fbdbc33e7b710dbd3ab48b62907ac7b5264b6568d5fb9757",
      "tests/test_r6_counterfactual_audits.py": "3b466b02c3fc7c65d9e7029f925249f789dcb4a440354a254778e15d64270ca8",
      "tests/test_r6_reproduction.py": "e35888f0947794e3f0c7169e56251252bd65324c82bcf8eae8d70572b0676cb1",
      "tests/test_r6_runner_boundary.py": "93099e5ad511d21f78ff88aa234ff42269db246d9d86b90be07af628a534588a",
      "tests/test_r6_structural_audits.py": "525853077ac14c2de4b95074557fa29e4f47b490f1979fd5d4d1b0cb587b71a7",
      "tests/test_r6_validation.py": "d5f878db813aa0e2d080612e4e7d2bb1c07db362ad87b8a46aff53ed98bf0681",
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
      "/provenance/raw_argv",
      "/phase_authorization",
      "/source_manifest/observed_workspace_imports"
    ],
    "semantic_argv_retained": true,
    "environment_contract_retained": true,
    "source_config_access_state_metric_hashes_retained": true,
    "exact_canonical_hash_equality": true,
    "two_equally_malformed_payloads_ineligible": true,
    "volatile_exclusions_apply_only_after_each_child_strict_eligibility": true,
    "volatile_exclusions_apply_only_to_scientific_canonical_compare": true,
    "volatile_exclusions_forbidden_in_child_eligibility_or_authority_validation": true
  },
  "atomic_failure_contract": {
    "main_and_launcher_top_level_transaction": true,
    "temporary_file_same_directory": true,
    "flush_and_fsync_before_replace": true,
    "non_overwrite_publish": true,
    "original_exception_never_masked": true,
    "secondary_capture_or_publication_error_recorded_without_replacing_original": true,
    "failure_artifact_name": "failure.json",
    "pre_output_root_failure_parent": "artifacts/calibration/.r22_pre_root_failures",
    "pre_output_root_filename": "<stage>.<process_uuid>.failure.json",
    "required_failure_stages": [
      "argument_resolution",
      "authority_capture",
      "output_root_validation",
      "phase_authorization",
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
      "refine-logs/CALIBRATION_PROTOCOL_R22_2026-07-23.md",
      "refine-logs/CALIBRATION_PROTOCOL_R5_2026-07-22.md",
      "refine-logs/CALIBRATION_PROTOCOL_R6_2026-07-22.md",
      "refine-logs/CALIBRATION_PROTOCOL_R7_2026-07-22.md",
      "refine-logs/CALIBRATION_PROTOCOL_R8_2026-07-23.md",
      "refine-logs/CALIBRATION_PROTOCOL_R9_2026-07-23.md",
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
      "tests/test_frozen_source_manifest_cross_process.py",
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
    "manifest_order": "lexicographic_posix_relative_path",
    "authority_payload_exact_keys": [
      "schema_version",
      "allowlist",
      "files"
    ],
    "manifest_exact_top_level_keys": [
      "schema_version",
      "allowlist",
      "files",
      "source_manifest_authority_sha256",
      "observed_workspace_imports"
    ],
    "authority_hash_field": "source_manifest_authority_sha256",
    "authority_hash_rule": "sha256_over_canonical_json_of_exact_schema_version_allowlist_files_payload_utf8_sort_keys_compact_ascii_no_nan",
    "observation_field": "observed_workspace_imports",
    "observation_rule": "process_local_sorted_unique_workspace_imports_must_be_subset_of_allowlist_but_are_excluded_from_authority_payload_and_hash",
    "cross_process_observation_equality_forbidden": true,
    "legacy_source_manifest_sha256_field_forbidden": true
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
    "dry_run_authorized": false,
    "closed_manifest_excluded_paths": [
      "refine-logs/CALIBRATION_PROTOCOL_R22_2026-07-23.md"
    ],
    "external_materializer_hashes_prebound_and_live_verified": true
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
      "refine-logs/CALIBRATION_PROTOCOL_R22_2026-07-23.md"
    ]
  },
  "freeze_record": {
    "schema_version": "r22_freeze_record_v1",
    "canonicalization": "utf8_json_sort_keys_compact_ascii_no_nan_v1",
    "registry_projection_excluded_json_pointers": [
      "/freeze_record"
    ],
    "closed_manifest_excluded_paths": [
      "refine-logs/CALIBRATION_PROTOCOL_R22_2026-07-23.md"
    ],
    "protocol_candidate_sha256": "c80104cf23d41dcf0e426c8e93b3fe6ebce27b85127b198ba49f3413026b0f24",
    "implementation_observation_sha256": "a2c796ee121805efc6fdc851cfcb534bdcfb8f10d9d8102382af1d2b888aee94",
    "runner_sha256": "2348f5e181fd5c9351777692c0b3f8cbe36a5178feccd8427547f1c737e0516d",
    "reproduction_launcher_sha256": "f02f17f1f679b8e621ecd5b36dc20d276fff54d9175136edfcb6886ca184ad90",
    "query_anchor_v2_runner_sha256": "60d04ca50c86598603491000907d3b1a97bd57d2d26532bc89fc1a7265b89e0d",
    "calibration_r5_sha256": "4d5f6569ae349c5fd99563f287fa9cc4c375484aa81a8fad149447bee8326537",
    "matching_sha256": "6186fa380093e984430f8170439f447026a52dab9bdf847b2cc1edf2d02b23ec",
    "runner_tests_sha256": "565d147c09cbb60a158b971f7c22b5875e0e863666e51b9aaa00e582db2ed5ad",
    "query_anchor_v2_tests_sha256": "366c9813c23c5d26fbdbc33e7b710dbd3ab48b62907ac7b5264b6568d5fb9757",
    "calibration_tests_sha256": "28fb9e90921e36c8cfc6795c4de12b2f125800369956cdf9b0f98e483f2feaa6",
    "matching_tests_sha256": "aaa90cdfe1e29c6b5bad8a644f4c1c56970031246226946f891d1139dc3dec5f",
    "semantic_validator_sha256": "07e179c046373b99c30118c09c821a7f896065b9ca41d354315b6c974ff6f3f8",
    "semantic_validator_tests_sha256": "d5f878db813aa0e2d080612e4e7d2bb1c07db362ad87b8a46aff53ed98bf0681",
    "boundary_tests_sha256": "93099e5ad511d21f78ff88aa234ff42269db246d9d86b90be07af628a534588a",
    "reproduction_tests_sha256": "e35888f0947794e3f0c7169e56251252bd65324c82bcf8eae8d70572b0676cb1",
    "gate_spec_sha256": "9ee58dd2053816d216bc5ed8d339fb4bb4488c092fccd090cd05bcbccd385715",
    "closed_manifest_sha256": "641a602ae2b8cf28d7552d85cd7dd88afccaa1850f78ca5703be4b6f1d51e56f",
    "canonical_registry_sha256": "4ea256a9eafe95cf6d08ce4bbe9ab5c6158b4993bcad4ed73dbc71e09953a072",
    "structural_audit_sha256": "334cc080343a96fb6173abe6cf6059b8b5ad1ac4c15d7c3051dc5609da1cb438",
    "structural_audit_tests_sha256": "525853077ac14c2de4b95074557fa29e4f47b490f1979fd5d4d1b0cb587b71a7",
    "summary_roundtrip_tests_sha256": "93099e5ad511d21f78ff88aa234ff42269db246d9d86b90be07af628a534588a"
  },
  "registry_composition": {
    "materialized_effective_registry": true,
    "runtime_loader_reads_this_object_directly": true,
    "runtime_loader_requires_base_registry_merge": false,
    "provenance_base_path": "refine-logs/CALIBRATION_PROTOCOL_R8_2026-07-23.md",
    "provenance_base_sha256": "9f360cc11ed50275482d419629205374bc83febe96f31dc73e93bc45c30f6291",
    "provenance_base_registry_sha256": "2a7129f670e5362fbdb8b8613707d39f51359606d7190e846b62777381595479",
    "provenance_base_registry_projection_sha256": "2efcf7e55b2d8c5fb78cd6a05af0fa4c3fcc25d37345e8e9287da4c802a2ad72",
    "unlisted_r8_values_materialized_exactly": true
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
    "r22_administrative_deltas": [
      "separate_source_manifest_authority_from_process_local_import_observation",
      "bind_certificates_claims_receipts_and_eligibility_to_authority_hash_only",
      "retain_closed_world_observed_import_subset_validation_per_process",
      "forbid_cross_process_observation_equality_as_authority",
      "forbid_legacy_ambiguous_source_manifest_sha256_field"
    ],
    "no_scientific_method_or_data_delta": true,
    "r21_failure_artifacts_metadata_only_ineligible_for_r22": true,
    "fresh_r22_authorization_claim_failure_and_reproduction_namespaces_only": true,
    "r14_v5_frozen_validator_bundle_and_all_r14_pins_unchanged": true,
    "no_dataset_model_download_or_formal_data_authorization": true,
    "no_gpu_slurm_or_allocation_4161_authorization": true
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
    "method_exact_r8": true,
    "data_exact_r8": true,
    "fixtures_exact_r8": true,
    "splits_exact_r8": true,
    "thresholds_exact_r8": true,
    "seeds_exact_r8": true,
    "optimizer_settings_exact_r8": true,
    "gate_order_exact_r8": true,
    "gate_thresholds_exact_r8": true,
    "counterfactuals_exact_r8": true,
    "exact64_model_interface_exact_r8": true,
    "data_access_contract_exact_r8": true,
    "formal_boundaries_exact_r8": true
  },
  "registered_r8_evidence": {
    "frozen_authority": {
      "protocol_path": "refine-logs/CALIBRATION_PROTOCOL_R8_2026-07-23.md",
      "protocol_sha256": "9f360cc11ed50275482d419629205374bc83febe96f31dc73e93bc45c30f6291",
      "materialized_registry_sha256": "2a7129f670e5362fbdb8b8613707d39f51359606d7190e846b62777381595479",
      "registry_projection_sha256": "2efcf7e55b2d8c5fb78cd6a05af0fa4c3fcc25d37345e8e9287da4c802a2ad72"
    },
    "dry_run": {
      "summary_path": "artifacts/calibration/capes_ci_qptm_r8_dryrun_20260723_v1/summary.json",
      "summary_sha256": "4189dde95cb5f65b4cb750882d16edeed4df14aacf24e46ed4b08d86f985d84a",
      "status": "DRY_RUN_VALIDATED_R8",
      "postrun_audit_path": "artifacts/calibration/capes_ci_qptm_r8_dryrun_20260723_v1/postrun_audit.json",
      "postrun_audit_file_sha256": "d0d7070a9c46774b2aa2c963d2241d5c1469c476834cc0cbf005dbdfd110fd04",
      "postrun_audit_self_sha256": "82d921e339bcbbbb8b9871bf2ee1b3392be149bc1fc83b8c10acd4bde7a9f585",
      "postrun_audit_self_hash_field": "audit_sha256",
      "postrun_audit_verdict": "PASS_R8_DRY_RUN_POSTRUN_AUDIT",
      "postrun_audit_passed": true,
      "eligible_engineering_evidence": true,
      "scientific_method_evidence": false
    },
    "smoke_seed17": {
      "failure_path": "artifacts/calibration/capes_ci_qptm_r8_smoke_seed17_20260723_v1/failure.json",
      "failure_sha256": "c9dcac95d20855794e2fc7251c339802b6e378f9bc6009f058ed98992a07d59f",
      "status": "TECHNICAL_FAILURE_R8_UNHANDLED_EXCEPTION",
      "stage": "summary_postserialization_validation",
      "exception_type": "RuntimeError",
      "summary_written": false,
      "launch_authorized_by_frozen_r8_protocol": false,
      "eligible": false,
      "scientific_method_evidence": false,
      "diagnostic_use_only": true,
      "diagnostic_boundary": {
        "may_support": [
          "identify_the_serialization_order_contract_defect",
          "define_the_single_r21_technical_semantic_correction",
          "design_fail_closed_phase_authorization_guards"
        ],
        "may_not_support": [
          "r8_smoke_survival",
          "any_gate_pass_or_fail_claim",
          "method_selection",
          "threshold_or_hyperparameter_change",
          "registered_local_authorization",
          "server_authorization",
          "formal_or_scientific_claim"
        ],
        "completed_gate_payloads_and_metrics_are_ineligible": true,
        "no_retrospective_authorization": true
      }
    }
  },
  "exact64_method_order": [
    "main",
    "local_independent",
    "hungarian",
    "sinkhorn"
  ],
  "exact64_method_order_contract": {
    "authority_json_pointer": "/exact64_method_order",
    "authority_is_json_array": true,
    "authority_array_order_is_semantic": true,
    "authority_array_values_unique": true,
    "authority_array_exact_value": [
      "main",
      "local_independent",
      "hungarian",
      "sinkhorn"
    ],
    "fair_baseline_summary_copy_json_pointer": "/fair_baseline_gate/exact64_method_order",
    "fair_baseline_summary_copy_must_equal_authority_array": true,
    "baseline_mapping_json_pointer_pattern": "/baseline_results/{seed}/{stratum}",
    "baseline_mapping_required_exact_key_set_from_authority_array": true,
    "baseline_mapping_json_object_iteration_order_semantic": false,
    "baseline_mapping_serialized_member_order_semantic": false,
    "producer_sequential_traversal_must_iterate_authority_array": true,
    "native_validator_sequential_traversal_must_iterate_authority_array": true,
    "independent_validator_sequential_traversal_must_iterate_authority_array": true,
    "baseline_method_order_exact_check_semantics": "mapping_key_set_equals_set_of_exact64_method_order_and_all_ordered_processing_follows_exact64_method_order",
    "comparing_list_of_mapping_keys_to_authority_is_forbidden": true,
    "json_sort_keys_serialization_must_not_change_semantic_verdict": true
  },
  "phase_authorization_contract": {
    "schema_version": "r22_phase_authorization_contract_v1",
    "external_materializers": {
      "registered_reproduction_authorizer": {
        "relative_path": ".tmp/audit_r22_registered.py",
        "sha256": "c2b5caec78f684cd572054c49024c93c91f1a6f4ca87804e836c614341428c0b",
        "sha256_rule": "sha256_over_exact_regular_file_bytes",
        "invocation": {
          "working_directory_relative": ".",
          "argv0_must_resolve_to_materializer_relative_path": true,
          "argv_tail": []
        }
      }
    },
    "external_materializer_provenance_rule": "each_independent_audit_materializer_must_bind_its_frozen_relative_path_exact_file_sha256_and_canonical_working_directory_argv0_argv_tail_invocation_in_audit_evidence_and_phase_certificate; runner_validation_compares_this_declared_identity_against_the_frozen_registry_without_extending_the_governed_source_allowlist",
    "authorization_root_relative": "artifacts/calibration/.r22_phase_authorizations",
    "authorization_root_must_be_inside_resolved_workspace": true,
    "authorization_files_must_be_regular_non_symlink_files": true,
    "certificate_canonicalization": "utf8_json_sort_keys_compact_ascii_no_nan_v1",
    "certificate_file_hash_algorithm": "sha256_over_exact_persisted_bytes",
    "protocol_hash_rule": "sha256_over_exact_final_frozen_protocol_file_bytes",
    "registry_hash_rule": "sha256_over_canonical_complete_first_json_object_including_non_null_freeze_record",
    "freeze_precheck_protocol_nonself_hash_rule": "sha256_of_exact_final_frozen_protocol_utf8_bytes_with_the_first_registry_freeze_record_replaced_by_json_null_and_no_other_byte_changes",
    "freeze_precheck_registry_nonself_hash_rule": "sha256_over_canonical_complete_first_json_object_after_removing_only_top_level_freeze_record",
    "source_manifest_hash_rule": "certificate_source_manifest_authority_sha256_equals_runner_source_manifest_authority_sha256_over_exact_schema_allowlist_files_including_final_protocol_with_process_local_observed_workspace_imports_excluded_from_authority",
    "certificate_self_hash_field": "certificate_self_sha256",
    "certificate_self_hash_rule": "sha256_of_canonical_certificate_after_removing_only_top_level_certificate_self_sha256",
    "certificate_self_hash_lowercase_hex_length": 64,
    "certificate_id_field": "certificate_id",
    "certificate_id_rule": "lowercase_canonical_uuid_version_4",
    "phase_nonce_field": "phase_nonce",
    "phase_nonce_rule": "64_lowercase_hex_characters_from_32_cryptographically_random_bytes",
    "certificate_creation_rule": "single registry-fixed regular certificate file is created only through the verified-parent-handle NtCreateFile FILE_CREATE transaction defined by safe_path_transaction_contract; canonical bytes are written flushed and reopened for identity/hash verification",
    "certificate_creation_requires_all_required_checks_true": true,
    "certificate_creation_is_one_shot": true,
    "certificate_replay_deletion_or_replacement_forbidden": true,
    "certificate_id_and_phase_nonce_required_in_every_certificate": true,
    "claims_subdirectory_relative": "artifacts/calibration/.r22_phase_authorizations/claims",
    "claim_schema_version": "r22_phase_authorization_claim_v1",
    "claim_path_rule": "ordinary_phase_claims_use_certificate_type_dot_certificate_id_dot_phase_nonce_dot_claim_json; independent_reproduction_claims_use_certificate_type_dot_certificate_id_dot_phase_nonce_dot_target_child_leaf_dot_claim_json",
    "claim_creation_rule": "single derived registry-fixed regular claim file is created only through the verified-parent-handle NtCreateFile FILE_CREATE transaction defined by safe_path_transaction_contract; canonical bytes are written flushed and reopened for identity/hash verification",
    "claim_self_hash_field": "claim_self_sha256",
    "claim_self_hash_rule": "sha256_of_canonical_claim_after_removing_only_top_level_claim_self_sha256",
    "claim_required_exact_top_level_keys": [
      "schema_version",
      "certificate_type",
      "certificate_id",
      "phase_nonce",
      "process_uuid",
      "target_phase",
      "target_child_leaf",
      "target_output_root_relative",
      "certificate_path",
      "certificate_file_sha256",
      "certificate_self_sha256",
      "protocol_sha256",
      "registry_sha256",
      "source_manifest_authority_sha256",
      "pre_root_target_absent",
      "claimed_utc",
      "claim_self_sha256"
    ],
    "claim_process_uuid_rule": "lowercase_canonical_uuid_version_4_equal_to_current_runner_process_uuid",
    "claim_is_one_shot": true,
    "claim_replay_forbidden_even_after_failure": true,
    "claim_deletion_or_replacement_forbidden": true,
    "concurrent_claim_attempts_exactly_one_can_succeed": true,
    "strict_exact_keys_types_values": true,
    "unknown_or_missing_keys_fail": true,
    "nonfinite_or_unresolved_values_fail": true,
    "issued_utc_requires_utc_z": true,
    "no_cli_or_environment_override": true,
    "runner_guard": {
      "execution_point": "after_frozen_protocol_and_registry_resolution_but_before_output_root_creation_model_construction_or_split_access",
      "authorization_denial_stage": "phase_authorization",
      "authorization_denial_status": "TECHNICAL_FAILURE_R22_PHASE_AUTHORIZATION",
      "denial_uses_pre_root_failure_parent": "artifacts/calibration/.r22_pre_root_failures",
      "denial_exit_nonzero": true,
      "denial_creates_no_phase_output_root": true,
      "certificate_path_is_registry_fixed": true,
      "all_preclaim_validation_completed_before_claim_creation": true,
      "certificate_snapshot_file_hash_and_self_hash_recomputed": true,
      "protocol_file_hash_and_full_registry_hash_recomputed_from_same_snapshot_bytes": true,
      "prerequisite_summary_and_audit_file_hashes_recomputed_from_same_snapshot_bytes": true,
      "prerequisite_audit_self_hash_recomputed_from_same_snapshot_bytes": true,
      "prerequisite_status_verdict_passed_and_all_checks_recomputed": true,
      "target_output_root_absent_checked_only_in_pre_root_guard_snapshot": true,
      "pre_root_absence_snapshot_must_be_true_before_claim": true,
      "claim_created_after_pre_root_absence_snapshot_and_all_other_checks": true,
      "claim_must_bind_current_process_uuid_target_certificate_exact_bytes_hash_and_certificate_self_hash": true,
      "existing_claim_is_replay_or_concurrency_failure": true,
      "terminal_strict_validation_uses_stored_pre_root_absence_snapshot_and_persisted_claim": true,
      "terminal_strict_validation_must_not_live_recompute_target_output_root_absence": true,
      "prepublication_recheck_excludes_target_output_root_absence": true,
      "prepublication_rechecks_only_bound_nonabsence_file_hashes_against_preclaim_snapshot": true,
      "summary_authorization_evidence_json_pointer": "/phase_authorization",
      "dry_run_summary_authorization_evidence_field_forbidden": true,
      "summary_authorization_evidence_required_fields": [
        "certificate_type",
        "certificate_path",
        "certificate_file_sha256",
        "certificate_self_sha256",
        "certificate_id",
        "phase_nonce",
        "claim_path",
        "claim_file_sha256",
        "claim_self_sha256",
        "claim_process_uuid",
        "protocol_sha256",
        "registry_sha256",
        "source_manifest_authority_sha256",
        "materializer_provenance",
        "target_phase",
        "target_output_root_relative",
        "target_child_leaf",
        "target_seeds",
        "target_steps",
        "target_device",
        "prerequisite_summary_sha256",
        "prerequisite_audit_file_sha256",
        "prerequisite_audit_self_sha256",
        "formal_data_authorization",
        "formal_test_used",
        "formal_claim_flags",
        "pre_root_target_absent_snapshot",
        "authorized",
        "authorization_status"
      ],
      "authorization_relative_path_derivation_accepts_absent_terminal_target_leaf_before_claim_or_mkdir": true,
      "authorization_relative_path_derivation_rule": "validate_all_existing_workspace_components_without_reparse_then_derive_canonical_relative_path_from_registered_absent_target_leaf_before_claim_or_mkdir",
      "reproduction_requires_child_certificate_map": true,
      "reproduction_launcher_must_invoke_registry_fixed_issuer_synchronously_before_parent_creation": true,
      "reproduction_launcher_issuer_has_no_cli_or_environment_override": true,
      "reproduction_child_summary_receipt_requires_certificate_and_claim": true,
      "reproduction_child_summary_receipt_requires_target_child_leaf": true,
      "phase_authorization_mode_closed_set": [
        "independent_reproduction"
      ],
      "phase_authorization_required_modes": [
        "independent_reproduction"
      ],
      "phase_authorization_denied_all_other_modes": true,
      "phase_classification_rule": "classify_as_independent_reproduction_iff_and_only_iff_run_dir_is_exactly_one_registered_child_root_under_target_output_parent_relative_and_cli_semantics_are_cpu_seeds_17_29_43_steps_500_without_dry_run_or_smoke; otherwise deny_before_parent_creation_claim_output_root_model_or_split_access",
      "independent_reproduction_child_certificate_type_map": {
        "process_a": "reproduction_process_a_authorization",
        "process_b": "reproduction_process_b_authorization"
      },
      "independent_reproduction_child_certificate_type_map_exact_keys": [
        "process_a",
        "process_b"
      ],
      "independent_reproduction_child_certificate_routing_rule": "select_only_by_exact_run_dir_child_leaf_then_require_the_exact_matching_child_certificate_type_and_registry_fixed_path; no fallback_default_or_single_shared_certificate_type_exists",
      "issuer_and_runner_require_final_frozen_authority": true,
      "summary_authorization_receipt_required_modes": [
        "independent_reproduction"
      ],
      "summary_authorization_receipt_forbidden_modes": [
        "dry_run",
        "smoke",
        "registered_local",
        "registered_slurm4161"
      ],
      "summary_authorization_receipt_mode_rule": "a persisted phase_authorization receipt is required iff mode is in the closed required list; it is forbidden iff mode is in the closed forbidden list; any other mode is denied before receipt, claim, parent creation, output-root creation, model construction, or split access",
      "reproduction_parent_creation_transaction_contract_ref": "/phase_authorization_contract/safe_path_transaction_contract/runner_native_directory_creation_requirement",
      "reproduction_launcher_must_reopen_and_validate_both_fixed_child_certificates_before_any_parent_creation_or_child_claim": true
    },
    "registered_postrun_audit_contract": {
      "schema_version": "r22_registered_postrun_audit_v1",
      "materializer_id": "registered_reproduction_authorizer",
      "self_hash_field": "audit_sha256",
      "self_hash_rule": "sha256_of_canonical_audit_after_removing_only_top_level_audit_sha256",
      "relative_path": "artifacts/calibration/.r22_phase_authorizations/r14_registered_local_postrun_audit.json",
      "required_exact_top_level_keys": [
        "schema_version",
        "run_dir",
        "passed",
        "verdict",
        "checks",
        "failed_checks",
        "evidence",
        "audit_sha256"
      ],
      "required_exact_check_keys": [
        "r14_registered_summary_file_hash_matches_live",
        "r14_registered_summary_bytes_parse_exact",
        "r14_registered_protocol_hash_matches_live",
        "r14_registered_registry_hash_matches_live",
        "r14_registered_summary_schema_exact",
        "r14_registered_summary_status_exact",
        "r14_registered_summary_strict_validation_passed",
        "r14_registered_completed_gates_zero_to_seven_exact",
        "r14_registered_only_independent_reproduction_not_run",
        "r14_registered_phase_authorization_receipt_valid",
        "r14_registered_formal_data_hold",
        "r14_registered_formal_test_unused",
        "r14_registered_formal_claim_flags_false",
        "r14_registered_output_root_exact",
        "r14_registered_device_cpu",
        "r14_registered_seeds_exact",
        "r14_registered_steps_exact",
        "r14_registered_materializer_provenance_matches_frozen_contract",
        "r14_provenance_comparator_origin_protocol_hash_matches",
        "r14_provenance_comparator_origin_registry_hash_matches",
        "r14_provenance_comparator_route_is_bundle_origin_only"
      ],
      "required_exact_verdicts": {
        "pass": "PASS_R22_REGISTERED_POSTRUN_AUDIT",
        "fail": "FAIL_R22_REGISTERED_POSTRUN_AUDIT"
      }
    },
    "reproduction_authorization": {
      "issuer_invocation": {
        "relative_path": ".tmp/audit_r22_registered.py",
        "working_directory_relative": ".",
        "argv_tail": [],
        "called_synchronously_by": "scripts/run_query_anchor_r4_reproduction.py",
        "before_parent_creation": true,
        "before_any_child_claim_or_model_construction_or_split_access": true,
        "launcher_must_validate_returncode_zero_and_reopen_both_certificates": true,
        "launcher_owned_issuer_transaction": true,
        "issuer_invoked_exactly_once": true,
        "issuer_retry_forbidden": true,
        "preissued_r22_audit_or_child_certificates_forbidden": true,
        "launcher_absent_parent_and_authority_namespace_precheck_required": true,
        "after_absent_parent_and_authority_namespace_precheck": true
      },
      "target_phase": "independent_reproduction",
      "target_output_parent_relative": "artifacts/calibration/capes_ci_qptm_r22_reproduction_local_20260723_v1",
      "target_child_leaf_names": [
        "process_a",
        "process_b"
      ],
      "target_output_root_relative_rule": "target_output_parent_relative_plus_slash_plus_target_child_leaf",
      "target_seeds": [
        17,
        29,
        43
      ],
      "target_steps": 500,
      "target_device": "cpu",
      "child_certificates": {
        "process_a": {
          "schema_version": "r22_reproduction_child_authorization_certificate_v1",
          "certificate_type": "reproduction_process_a_authorization",
          "relative_path": "artifacts/calibration/.r22_phase_authorizations/reproduction_process_a_authorization.json",
          "target_output_root_relative": "artifacts/calibration/capes_ci_qptm_r22_reproduction_local_20260723_v1/process_a"
        },
        "process_b": {
          "schema_version": "r22_reproduction_child_authorization_certificate_v1",
          "certificate_type": "reproduction_process_b_authorization",
          "relative_path": "artifacts/calibration/.r22_phase_authorizations/reproduction_process_b_authorization.json",
          "target_output_root_relative": "artifacts/calibration/capes_ci_qptm_r22_reproduction_local_20260723_v1/process_b"
        }
      },
      "prerequisite_phase": "registered_local_r14",
      "prerequisite_summary_path": "artifacts/calibration/capes_ci_qptm_r14_registered_local_20260723_v1/summary.json",
      "prerequisite_summary_sha256": "bdf1b4609593dda3833ab1e06489d50fddc0e7085d254b42a0d82a789491b8cb",
      "prerequisite_summary_status": "PASS_R14_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
      "prerequisite_audit_path": "artifacts/calibration/.r22_phase_authorizations/r14_registered_local_postrun_audit.json",
      "prerequisite_audit_schema_version": "r22_registered_postrun_audit_v1",
      "prerequisite_audit_verdict": "PASS_R22_REGISTERED_POSTRUN_AUDIT",
      "prerequisite_audit_self_hash_field": "audit_sha256",
      "formal_data_authorization_expected": "HOLD",
      "formal_test_used_expected": false,
      "formal_claim_flags_expected": {
        "formal_claim_allowed": false,
        "formal_ablation_claim_allowed": false,
        "full_method_claim_allowed": false
      },
      "authorization_status": "AUTHORIZED_R22_INDEPENDENT_REPRODUCTION",
      "child_certificate_required_exact_top_level_keys": [
        "schema_version",
        "certificate_type",
        "certificate_id",
        "phase_nonce",
        "protocol_id",
        "protocol_sha256",
        "registry_sha256",
        "source_manifest_authority_sha256",
        "materializer_provenance",
        "target_phase",
        "target_output_parent_relative",
        "target_child_leaf",
        "target_output_root_relative",
        "target_seeds",
        "target_steps",
        "target_device",
        "prerequisite_summary_path",
        "prerequisite_summary_sha256",
        "prerequisite_audit_path",
        "prerequisite_audit_file_sha256",
        "prerequisite_audit_self_sha256",
        "prerequisite_audit_verdict",
        "prerequisite_audit_passed",
        "formal_data_authorization",
        "formal_test_used",
        "formal_claim_flags",
        "checks",
        "authorized",
        "authorization_status",
        "issued_utc",
        "certificate_self_sha256"
      ],
      "child_certificate_required_exact_check_keys": [
        "frozen_protocol_hash_matches_live",
        "frozen_protocol_nonself_projection_hash_matches_freeze_record",
        "full_registry_hash_matches_live",
        "registry_nonself_projection_hash_matches_freeze_record",
        "source_manifest_authority_hash_matches_live",
        "audit_materializer_provenance_matches_frozen_contract",
        "r14_registered_summary_file_hash_matches_live",
        "r14_registered_summary_status_exact",
        "r14_registered_summary_strict_validation_passed",
        "r14_registered_audit_file_hash_matches_live",
        "r14_registered_audit_self_hash_valid",
        "r14_registered_audit_schema_exact",
        "r14_registered_audit_verdict_exact",
        "r14_registered_audit_passed_true",
        "r14_registered_audit_failed_checks_empty",
        "formal_data_hold",
        "formal_test_unused",
        "formal_claim_flags_false",
        "certificate_path_registry_fixed",
        "target_parent_absent_at_certificate_issuance",
        "target_output_root_absent_at_certificate_issuance",
        "target_child_leaf_exact"
      ],
      "child_certificate_authorization_rule": "each_child_certificate_is_independently_one_shot_and_authorizes_exactly_its_fixed_child_leaf_and_root_only_after_the_strict_r14_registered_summary_audit_passes",
      "pair_issuance_rule": "issuer_must_create_exactly_the_two_registry_fixed_child_certificates_with_distinct_uuid4_certificate_ids_and_distinct_nonces_using_the_verified-parent-handle_NtCreateFile_FILE_CREATE_transaction; a partial pair is terminal_ineligible_and_neither_child_may_launch",
      "child_claim_rule": "each child consumes only its matching certificate through one verified-parent-handle_NtCreateFile_FILE_CREATE_claim whose exact receipt binds certificate bytes hash nonce target_child_leaf and target_output_root_relative; a certificate or claim for one child never authorizes the other",
      "target_parent_absent_at_issuer_entry": true,
      "target_children_absent_at_issuer_entry": true,
      "post_certificate_parent_creation_transaction_contract_ref": "/phase_authorization_contract/safe_path_transaction_contract/runner_native_directory_creation_requirement",
      "schema_version": "r22_reproduction_authorization_certificate_v1",
      "relative_path": "artifacts/calibration/.r22_phase_authorizations/reproduction_authorization.json",
      "launcher_owned_issuer_transaction_contract": {
        "transaction_owner": "scripts/run_query_anchor_r4_reproduction.py",
        "issuer_invocation_count_exact": 1,
        "synchronous": true,
        "retry_allowed": false,
        "preissued_r22_audit_allowed": false,
        "preissued_r22_child_certificates_allowed": false,
        "required_precheck_order": [
          "target_output_parent_absent",
          "r22_authority_namespace_absent",
          "r22_registered_audit_absent",
          "r22_process_a_certificate_absent",
          "r22_process_b_certificate_absent"
        ],
        "issuer_invocation_after_all_prechecks": true,
        "issuer_success_and_two_certificate_reopen_before_parent_creation": true,
        "partial_issuance_or_nonzero_exit_is_terminal_no_retry": true,
        "r20_authority_namespace_is_forensic_only_and_never_read_as_r22_authority": true,
        "r21_authority_namespace_is_forensic_only_and_never_read_as_r22_authority": true
      },
      "issuing_materializer_id": "registered_reproduction_authorizer",
      "source_manifest_authority_contract": {
        "field": "source_manifest_authority_sha256",
        "schema_version": "r22_source_manifest_v1",
        "manifest_exact_top_level_keys": [
          "schema_version",
          "allowlist",
          "files",
          "source_manifest_authority_sha256",
          "observed_workspace_imports"
        ],
        "payload_exact_keys": [
          "schema_version",
          "allowlist",
          "files"
        ],
        "observation_field": "observed_workspace_imports",
        "observation_excluded_from_authority": true,
        "cross_process_observation_equality_forbidden": true,
        "legacy_source_manifest_sha256_field_forbidden": true,
        "required_consumers": [
          "issuer_materializer",
          "launcher_reopen",
          "runner_preclaim",
          "runner_child_eligibility",
          "runner_summary_receipt",
          "runner_prepublication"
        ]
      }
    },
    "freeze_preconditions": {
      "authority_state_must_be_frozen_before_issuer_or_runner": "FROZEN_BEFORE_R22_REPRODUCTION",
      "external_materializer_sha256_must_be_64_lowercase_hex_before_freeze": true,
      "external_materializer_path_must_be_regular_nonreparse_file": true,
      "external_materializer_live_file_bytes_sha256_must_equal_registry_before_freeze": true,
      "issuer_and_runner_must_recompute_frozen_protocol_and_registry_hashes_before_enablement": true
    },
    "safe_path_transaction_contract": {
      "platform": "Windows",
      "scope": "issuer_authorization_root_certificate_files_reproduction_parent_child_claim_files_and_child_output_roots",
      "path_component_rule": "every existing workspace component is opened with FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT and rejected if FILE_ATTRIBUTE_REPARSE_POINT or symlink; raw lexical path must match the registry exactly",
      "identity_rule": "capture and recheck VolumeSerialNumber plus FILE_ID_128 (or equivalent volume-and-file-index identity) for each opened parent and terminal component immediately before and immediately after every security-sensitive operation",
      "directory_creation_rule": "the only permitted native directory-create primitive is NtCreateFile with RootDirectory equal to an already verified nonreparse parent HANDLE, OBJECT_ATTRIBUTES containing only the relative child name and OBJ_DONT_REPARSE, CreateDisposition FILE_CREATE, and CreateOptions FILE_DIRECTORY_FILE|FILE_OPEN_REPARSE_POINT; there is no absolute-path CreateDirectoryW/mkdir/path fallback. Reopen by verified handle, require no reparse attribute, and recheck parent plus new child VolumeSerialNumber and FILE_ID_128 before proceeding",
      "certificate_and_claim_creation_rule": "certificate and claim regular files are security-sensitive creations and must use NtCreateFile with RootDirectory equal to their already verified nonreparse parent HANDLE, OBJECT_ATTRIBUTES containing only the relative regular-file leaf plus OBJ_DONT_REPARSE, CreateDisposition FILE_CREATE, and FILE_OPEN_REPARSE_POINT; write canonical bytes through that returned handle, FlushFileBuffers, reopen through the verified parent handle, then identity and hash recheck. No CreateFileW absolute-path fallback and no creation outside the verified-handle scope exists",
      "handle_relative_equivalent_rule": "all security-sensitive directory certificate and claim creation is rooted at the verified parent HANDLE with a relative child name plus OBJ_DONT_REPARSE. No absolute-path or lexical-path fallback is permitted",
      "issuer_order": "before parent creation: verify final frozen authority and materializer hash, verify absent parent and child roots, create strict audit then exactly two child certificates using the same verified-handle NtCreateFile transaction; partial certificate pair is terminal and no child launch is allowed",
      "runner_order": "before parent creation: verify final frozen authority, issuer subprocess receipt, both certificate snapshots and identities, then use only the referenced verified-handle NtCreateFile transaction; before each child claim and child root creation revalidate parent identity and matching child certificate snapshot; child A never authorizes B",
      "reparse_or_identity_change_response": "abort pre-root with TECHNICAL_FAILURE_R22_PHASE_AUTHORIZATION and create no affected child output root",
      "runner_native_directory_creation_requirement": {
        "native_primitive": "NtCreateFile",
        "root_directory": "verified_nonreparse_parent_HANDLE",
        "object_attributes": "relative_child_name_plus_OBJ_DONT_REPARSE",
        "create_disposition": "FILE_CREATE",
        "create_options": [
          "FILE_DIRECTORY_FILE",
          "FILE_OPEN_REPARSE_POINT"
        ],
        "absolute_path_fallback_forbidden": true,
        "identity_checks": [
          "parent_volume_serial_and_file_id_128_before",
          "parent_volume_serial_and_file_id_128_after",
          "new_child_volume_serial_and_file_id_128_after_open"
        ],
        "failure_rule": "any native create failure reparse attribute or identity mismatch aborts pre-root and creates no affected child output root"
      },
      "required_negative_tests": [
        "junction_or_symlink_in_authorization_or_parent_chain_denied_before_claim",
        "parent_handle_identity_swap_before_native_create_denied_before_child_root",
        "new_child_reparse_attribute_after_native_create_denied_before_child_root",
        "existing_child_or_existing_claim_is_terminal_replay_denied",
        "absolute_path_directory_create_fallback_is_absent_and_rejected_by_static_test",
        "process_a_certificate_or_claim_cannot_authorize_process_b"
      ]
    },
    "external_materializer_inventory_v1": [
      {
        "materializer_id": "registered_reproduction_authorizer",
        "relative_path": ".tmp/audit_r22_registered.py",
        "roles": [
          "registered_postrun_audit",
          "reproduction_authorization"
        ]
      }
    ],
    "frozen_validator_dependency_bundle": {
      "schema_version": "r16_frozen_r14_validator_dependency_bundle_v1",
      "bundle_relative_directory": ".tmp/r16_frozen_r14_validator_bundle_v5",
      "manifest_relative_path": ".tmp/r16_frozen_r14_validator_bundle_v5/manifest.json",
      "manifest_sha256": "bb2f39399a95d3c51fa34c6ee46bb34a79650ac4b2d5c667d87c765ea6e2720a",
      "origin_protocol": {
        "relative_path": "refine-logs/CALIBRATION_PROTOCOL_R14_2026-07-23.md",
        "sha256": "11192f98ea1dcc216a6b13eb1611c8cb9ef677d75500032b6cbdf38528e125ce",
        "registry_sha256": "8e6d8bc79ef210eda9182167ec8328f8b0641cfcb69e75dbc1d56a1ab1f98f5e",
        "authority_state": "FROZEN_BEFORE_R14_DRY_RUN"
      },
      "required_file_sha256": {
        "refine-logs/CALIBRATION_PROTOCOL_R5_2026-07-22.md": "015949a51b06c1da6c0c10b881226979b412d4cac460f6b2e5779db6ac7b4491",
        "refine-logs/CALIBRATION_PROTOCOL_R13_2026-07-23.md": "cea5d04fd8a84c4e42dad523c4e89ff532622c5b91f79dcf7d017bb217ed8459",
        "refine-logs/CALIBRATION_PROTOCOL_R14_2026-07-23.md": "11192f98ea1dcc216a6b13eb1611c8cb9ef677d75500032b6cbdf38528e125ce",
        "scripts/run_query_anchor_r4.py": "53b511f27a2baee1fd20b7536a1a76b631b64667cacc1abb1886c887f7370f6a",
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
        "src/visualvit/r6_validation.py": "7afddde0dff6bca2d51cfedaf72676cbb8ad68a3f37626f80f5b8770ec4892a2",
        "src/visualvit/schemas.py": "e91fdb17498bbcca72f31b6859398988cb75e9f5c4a908e0b9a34ca08a2e4ed9",
        "src/visualvit/statistics.py": "0d29aa4216870b7272a4fbec39fef4e5a64249cbc8205b1e4336659989dafc74",
        "src/visualvit/tokenizer.py": "defb9aeddeb2225362d890590a984f26d84cd3840acc8105c4444b2ff096506d"
      },
      "bundle_file_set_rule": "exactly_the_registered_required_file_sha256_keys_plus_manifest_json_no_pycache_no_symlink_no_junction",
      "module_loading_rule": "audit_purges_scripts_and_visualvit_modules_then_loads_only_from_bundle_relative_directory_with_live_workspace_src_and_scripts_paths_forbidden_and_no_fallback_imports",
      "required_validator_module": "scripts.run_query_anchor_r4",
      "required_semantic_validator_module": "visualvit.r6_validation",
      "live_workspace_dependency_forbidden": true,
      "bundle_must_be_regular_nonreparse_tree": true,
      "freeze_required_before_audit_or_issuer": true
    },
    "r14_provenance_comparator_routing": {
      "schema_version": "r22_r14_provenance_comparator_routing_v1",
      "subject": "registered_r14_evidence.registered_local",
      "authoritative_comparator_route": "phase_authorization_contract.frozen_validator_dependency_bundle.origin_protocol",
      "required_agreement_paths": [
        "/phase_authorization_contract/frozen_validator_dependency_bundle/origin_protocol",
        "/registered_r14_evidence/protocol"
      ],
      "origin_protocol_sha256": "11192f98ea1dcc216a6b13eb1611c8cb9ef677d75500032b6cbdf38528e125ce",
      "origin_registry_sha256": "8e6d8bc79ef210eda9182167ec8328f8b0641cfcb69e75dbc1d56a1ab1f98f5e",
      "reject_r16_direct_base_as_r14_comparator": true,
      "all_other_r16_execution_routing_is_unchanged": true
    },
    "materializer_id_consistency_contract": {
      "scope": "reproduction_authorization_materializer_identity",
      "canonical_registry_key": "issuing_materializer_id",
      "canonical_registry_pointer": "/phase_authorization_contract/reproduction_authorization/issuing_materializer_id",
      "canonical_value": "registered_reproduction_authorizer",
      "required_consumers": [
        "issuer_materializer",
        "launcher_reopen",
        "runner_preclaim",
        "runner_summary_receipt",
        "runner_prepublication"
      ],
      "consumer_value_rule": "every_required_consumer_must_read_the_canonical_registry_key_directly_and_compare_exactly_against_materializer_provenance_materializer_id",
      "alias_keys_forbidden": [
        "issuer_materializer_id"
      ],
      "alias_fallback_forbidden": true,
      "missing_or_nonexact_canonical_key_is_terminal": true,
      "scientific_contract_delta": false
    },
    "source_manifest_observation_rule": "each_consumer_independently_requires_observed_workspace_imports_subset_of_allowlist_without_cross_process_observation_equality",
    "source_manifest_authority_contract": {
      "field": "source_manifest_authority_sha256",
      "schema_version": "r22_source_manifest_v1",
      "manifest_exact_top_level_keys": [
        "schema_version",
        "allowlist",
        "files",
        "source_manifest_authority_sha256",
        "observed_workspace_imports"
      ],
      "payload_exact_keys": [
        "schema_version",
        "allowlist",
        "files"
      ],
      "observation_field": "observed_workspace_imports",
      "observation_excluded_from_authority": true,
      "cross_process_observation_equality_forbidden": true,
      "legacy_source_manifest_sha256_field_forbidden": true,
      "required_consumers": [
        "issuer_materializer",
        "launcher_reopen",
        "runner_preclaim",
        "runner_child_eligibility",
        "runner_summary_receipt",
        "runner_prepublication"
      ]
    }
  },
  "scientific_invariance_contract": {
    "comparison_base_protocol_sha256": "11192f98ea1dcc216a6b13eb1611c8cb9ef677d75500032b6cbdf38528e125ce",
    "comparison_base_materialized_registry_sha256": "8e6d8bc79ef210eda9182167ec8328f8b0641cfcb69e75dbc1d56a1ab1f98f5e",
    "exact_equal_json_pointers": [
      "/evidence_class",
      "/gate_order",
      "/run_modes",
      "/runtime_contract",
      "/resolver_contract",
      "/initialization_evidence_contract",
      "/structural_microcase_contract",
      "/full_chain_counterfactual_contract",
      "/metric_evidence_contract",
      "/reproduction_contract/canonical_json",
      "/reproduction_contract/canonical_path_normalization",
      "/reproduction_contract/environment_contract_retained",
      "/reproduction_contract/exact_canonical_hash_equality",
      "/reproduction_contract/fresh_process_count",
      "/reproduction_contract/primary_must_be_strictly_eligible",
      "/reproduction_contract/replica_b_launch_requires_replica_a_exit_zero_and_exact_pending_status_and_strict_eligibility",
      "/reproduction_contract/semantic_argv_retained",
      "/reproduction_contract/sequential_order",
      "/reproduction_contract/source_config_access_state_metric_hashes_retained",
      "/reproduction_contract/two_equally_malformed_payloads_ineligible",
      "/data_access_contract",
      "/formal_boundaries",
      "/query_nll_canonical_arithmetic_contract",
      "/initialization_runtime_state_hash_contract"
    ],
    "method_unchanged": true,
    "thresholds_unchanged": true,
    "seeds_unchanged": true,
    "splits_unchanged": true,
    "gate_order_and_survival_logic_unchanged": true,
    "formal_boundaries_unchanged": true,
    "only_technical_semantic_delta": "explicit_exact64_method_order_array_is_order_authority_while_baseline_json_object_member_order_is_nonsemantic",
    "phase_authorization_delta_is_execution_control_only": true,
    "administrative_delta_json_pointers": [
      "/reproduction_contract/volatile_exclusion_paths",
      "/reproduction_contract/volatile_exclusions_apply_only_after_each_child_strict_eligibility",
      "/reproduction_contract/volatile_exclusions_apply_only_to_scientific_canonical_compare",
      "/reproduction_contract/volatile_exclusions_forbidden_in_child_eligibility_or_authority_validation"
    ],
    "administrative_delta_scope": "reproduction_projection_only_after_each_child_strict_eligibility"
  },
  "registered_r9_evidence": {
    "protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R9_2026-07-23.md",
      "sha256": "c11a9c6677909c8ecab6645cf4d7aa79e3b7470aee573fb7e6c4a857dda00f8b",
      "registry_sha256": "bdb7ce728301f05169f6c07eb1896d9925d1ceb27311725d9ab9aca16d48acde",
      "authority_state": "FROZEN_BEFORE_R9_DRY_RUN"
    },
    "dry_run": {
      "summary_path": "artifacts/calibration/capes_ci_qptm_r9_dryrun_20260723_v1/summary.json",
      "summary_sha256": "d027a2d7556d30f0ba966ec6653be87aa3cf32c8f8e8a45ffa4fcf27f7b3af7f",
      "status": "DRY_RUN_VALIDATED_R9",
      "postrun_audit_path": "artifacts/calibration/capes_ci_qptm_r9_dryrun_20260723_v1/postrun_audit.json",
      "postrun_audit_file_sha256": "de670d8d8946ddf43d0870811695b45a56724533eaaf13623a91a3f32fdaae95",
      "postrun_audit_self_sha256": "3ccce3fb7431e2dea7cbf91c8df9cb661efe251813c334bcf0a2641667dc0e3f",
      "postrun_audit_verdict": "PASS_R9_DRY_RUN_POSTRUN_AUDIT",
      "eligible_engineering_evidence": true,
      "scientific_method_evidence": false
    },
    "smoke_seed17": {
      "failure_path": "artifacts/calibration/.r9_pre_root_failures/phase_authorization.e392e8a5-79d5-4292-a8ca-48b731d66330.failure.json",
      "failure_sha256": "708e8a1e82fd704979eb5e2c4f794905e652afd464d42ac75eb5f948d562d77c",
      "status": "TECHNICAL_FAILURE_R9_PHASE_AUTHORIZATION",
      "stage": "phase_authorization",
      "summary_written": false,
      "target_output_root_created": false,
      "invalid_reason": "r9_authorization_relative_path_derivation_required_the_absent_registered_target_leaf_before_claim_or_mkdir",
      "eligible_engineering_evidence": false,
      "scientific_method_evidence": false
    }
  },
  "registered_r10_evidence": {
    "protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R10_2026-07-23.md",
      "sha256": "261863f52942f695ce996c1b692defd924e7876716cc9338a7fe82523dfedf89",
      "registry_sha256": "131484e3124579f31fe6d63241c29bfda13902bc12b9249610b12086ee51ec13",
      "authority_state": "FROZEN_BEFORE_R10_DRY_RUN"
    },
    "registered_local": {
      "summary_path": "artifacts/calibration/capes_ci_qptm_r10_registered_local_20260723_v1/summary.json",
      "summary_sha256": "a337f81868f20aa94cc3c3b11d7f333e3729c68cdbe63f16fffedd1fb1b8b566",
      "summary_schema_version": "r10_summary_v1",
      "status": "PASS_R10_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
      "completed_gates": [
        "resolution_freeze",
        "structural_input",
        "fixture_identifiability",
        "transport_competence",
        "anti_equivalence",
        "mediator_recovery",
        "fair_baseline",
        "exact64_bridge"
      ],
      "not_run_gates": [
        "independent_reproduction"
      ],
      "eligible_engineering_evidence": true,
      "scientific_method_evidence": false
    },
    "reproduction_process_a_pre_root_failure": {
      "failure_path": "artifacts/calibration/.r10_pre_root_failures/phase_authorization.f4ffd0ee-8ba4-4d05-b63b-56705799acff.failure.json",
      "failure_sha256": "54b17e337181012e6145c54097c86a207588b7d8df7a78b158216e6793ad9672",
      "status": "TECHNICAL_FAILURE_R10_PHASE_AUTHORIZATION",
      "stage": "phase_authorization",
      "summary_written": false,
      "target_output_root_created": false,
      "invalid_reason": "r10_registered_certificate_target_was_fixed_to_original_registered_root_and_could_not_authorize_reproduction_process_a",
      "eligible_engineering_evidence": false,
      "scientific_method_evidence": false
    }
  },
  "registered_r11_evidence": {
    "protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R11_2026-07-23.md",
      "sha256": "13cd03e3b48371655f91770cf497c598cabcccd51e3ee0a8972ea4571486d058",
      "registry_sha256": "0178fba1a99c6c9c72e4b56476a1f6f48da16057234be523992cfd500e462853",
      "authority_state": "FROZEN_BEFORE_R11_REPRODUCTION"
    },
    "freeze_record": {
      "schema_version": "r11_freeze_record_v1",
      "canonicalization": "utf8_json_sort_keys_compact_ascii_no_nan_v1",
      "registry_projection_excluded_json_pointers": [
        "/freeze_record"
      ],
      "closed_manifest_excluded_paths": [
        "refine-logs/CALIBRATION_PROTOCOL_R11_2026-07-23.md"
      ],
      "protocol_candidate_sha256": "bb20f7a98eea009bf490f48df44d8e25c7b5b4148078248dcbb70c1784aaadc6",
      "implementation_observation_sha256": "111974807ad656f76e578113ca3c6a39e3874554b0cf460ed67d1e61bfaf3741",
      "runner_sha256": "888f4c0c597348aa063aa3bc4c5653b77df4bb7d3d75bc0bd9c40a58fd1e1383",
      "reproduction_launcher_sha256": "4517203a4c5fadaf17ef9c79b3645b696eab92a53b706b0e9f8e7af0841bb5dc",
      "query_anchor_v2_runner_sha256": "60d04ca50c86598603491000907d3b1a97bd57d2d26532bc89fc1a7265b89e0d",
      "calibration_r5_sha256": "4d5f6569ae349c5fd99563f287fa9cc4c375484aa81a8fad149447bee8326537",
      "matching_sha256": "6186fa380093e984430f8170439f447026a52dab9bdf847b2cc1edf2d02b23ec",
      "runner_tests_sha256": "ac7a75f21f5f4cb2aa0fea1d7fb2bac075af9eb6129b167f13f8807da7aef55d",
      "query_anchor_v2_tests_sha256": "366c9813c23c5d26fbdbc33e7b710dbd3ab48b62907ac7b5264b6568d5fb9757",
      "calibration_tests_sha256": "28fb9e90921e36c8cfc6795c4de12b2f125800369956cdf9b0f98e483f2feaa6",
      "matching_tests_sha256": "aaa90cdfe1e29c6b5bad8a644f4c1c56970031246226946f891d1139dc3dec5f",
      "semantic_validator_sha256": "df04765b668300a84a8391299d673e20322a38280170a523ce01022fcdbaf1bc",
      "semantic_validator_tests_sha256": "d6f94de4819d83b5770ab11cc0c769aed0f380edac8ce23913afb8b8599ee220",
      "boundary_tests_sha256": "60c895940d0f34927f44b6e1774244aba53c0d8c3ffe8fc39a05ddcc6daa39f2",
      "reproduction_tests_sha256": "d9ba5b5d9f022ea0aff53f02a9b97fa37a580e966b03d97391f266b20f68f2be",
      "gate_spec_sha256": "9ee58dd2053816d216bc5ed8d339fb4bb4488c092fccd090cd05bcbccd385715",
      "structural_audit_sha256": "334cc080343a96fb6173abe6cf6059b8b5ad1ac4c15d7c3051dc5609da1cb438",
      "structural_audit_tests_sha256": "525853077ac14c2de4b95074557fa29e4f47b490f1979fd5d4d1b0cb587b71a7",
      "summary_roundtrip_tests_sha256": "60c895940d0f34927f44b6e1774244aba53c0d8c3ffe8fc39a05ddcc6daa39f2",
      "closed_manifest_sha256": "2cf109a618c6f4d04989035103c2ee30d9ee8aff33c72f4f2fb91c39dbcf7607",
      "canonical_registry_sha256": "a3f08532e8e4f2d0ea4b1f6c155aa048aa3e20148f277a8db330fdce241bea1b"
    },
    "gate0_resolution_preflight_failure": {
      "failure_path": "artifacts/calibration/.r11_pre_root_failures/authority_capture.24e6bd45-9c12-49eb-a6bc-e0de8b600007.failure.json",
      "failure_sha256": "ad1f40e81cf40f290a934a7848e72346c2ab11a3fe82af5ced1f40129db98a55",
      "status": "STOP_R11_RESOLUTION_FREEZE",
      "stage": "authority_capture",
      "exception_type": null,
      "exception_message": null,
      "summary_written": false,
      "target_output_root_created": false,
      "eligible_engineering_evidence": false,
      "scientific_method_evidence": false
    },
    "relative_path_preflight_failure": {
      "failure_path": "artifacts/calibration/.r11_pre_root_failures/output_root_validation.cc41ba88-eb73-473f-802c-63e493ae146c.failure.json",
      "failure_sha256": "bea17987ed041421c9c8830caf4cfc9767b8ab050b263fc0b758d751bdb63c38",
      "status": "TECHNICAL_FAILURE_R11_UNHANDLED_EXCEPTION",
      "stage": "output_root_validation",
      "exception_type": "ValueError",
      "exception_message": "R10 output-root contract failed: {\"checks\": {\"inside_resolved_workspace\": true, \"leaf_exact\": true, \"output_root_absent\": true, \"parent_exact\": true, \"parent_is_directory\": true, \"parent_not_symlink\": true, \"parent_writable\": true, \"plain_workspace_ancestor_chain\": true, \"raw_path_absolute\": false, \"raw_path_has_no_dot_segments\": true, \"raw_path_lexically_exact_including_case\": false, \"registered_reproduction_child_topology\": true, \"reproduction_parent_not_symlink\": true, \"resolved_path_exact\": true}, \"expected_leaf\": \"capes_ci_qptm_r11_dryrun_20260723_v1\", \"expected_lexical_output_root\": \"E:\\\\Xiyaowang\\\\050_VisualVIT\\\\artifacts\\\\calibration\\\\capes_ci_qptm_r11_dryrun_20260723_v1\", \"expected_output_root\": \"E:\\\\Xiyaowang\\\\050_VisualVIT\\\\artifacts\\\\calibration\\\\capes_ci_qptm_r11_dryrun_20260723_v1\", \"expected_parent\": \"E:\\\\Xiyaowang\\\\050_VisualVIT\\\\artifacts\\\\calibration\", \"passed\": false, \"raw_requested_output_root\": \"artifacts\\\\calibration\\\\capes_ci_qptm_r11_dryrun_20260723_v1\", \"reproduction_child\": false, \"requested_output_root\": \"E:\\\\Xiyaowang\\\\050_VisualVIT\\\\artifacts\\\\calibration\\\\capes_ci_qptm_r11_dryrun_20260723_v1\", \"workspace\": \"E:\\\\Xiyaowang\\\\050_VisualVIT\"}",
      "summary_written": false,
      "target_output_root_created": false,
      "eligible_engineering_evidence": false,
      "scientific_method_evidence": false
    },
    "dry_run_pre_root_phase_authorization_failure": {
      "failure_path": "artifacts/calibration/.r11_pre_root_failures/phase_authorization.925d0146-9d1f-4e54-b076-4d4c01cf05b5.failure.json",
      "failure_sha256": "9d0479b67c7a73da35792caa3ebd52ad03cc84d121c2d58c58ec6b184269577e",
      "status": "TECHNICAL_FAILURE_R11_PHASE_AUTHORIZATION",
      "stage": "phase_authorization",
      "exception_type": "RuntimeError",
      "exception_message": "R11 phase authorization denied: R11 authorizes only the closed reproduction mode, not dry_run",
      "summary_written": false,
      "target_output_root_created": false,
      "eligible_engineering_evidence": false,
      "scientific_method_evidence": false
    },
    "interpretation": "all_r11_pre_root_failures_are_immutable_technical_or_resolution_evidence_only_and_are_ineligible_for_phase_survival_gate_method_threshold_server_or_scientific_inference"
  },
  "r11_scientific_contract_byte_identity": {
    "parent_protocol_sha256": "13cd03e3b48371655f91770cf497c598cabcccd51e3ee0a8972ea4571486d058",
    "parent_registry_sha256": "0178fba1a99c6c9c72e4b56476a1f6f48da16057234be523992cfd500e462853",
    "exact_equal_json_pointers": [
      "/evidence_class",
      "/gate_order",
      "/run_modes",
      "/runtime_contract",
      "/resolver_contract",
      "/initialization_evidence_contract",
      "/structural_microcase_contract",
      "/full_chain_counterfactual_contract",
      "/metric_evidence_contract",
      "/reproduction_contract",
      "/data_access_contract",
      "/formal_boundaries",
      "/query_nll_canonical_arithmetic_contract",
      "/initialization_runtime_state_hash_contract"
    ],
    "required": true
  },
  "registered_r14_evidence": {
    "protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R14_2026-07-23.md",
      "sha256": "11192f98ea1dcc216a6b13eb1611c8cb9ef677d75500032b6cbdf38528e125ce",
      "registry_sha256": "8e6d8bc79ef210eda9182167ec8328f8b0641cfcb69e75dbc1d56a1ab1f98f5e",
      "authority_state": "FROZEN_BEFORE_R14_DRY_RUN"
    },
    "registered_local": {
      "summary_path": "artifacts/calibration/capes_ci_qptm_r14_registered_local_20260723_v1/summary.json",
      "summary_sha256": "bdf1b4609593dda3833ab1e06489d50fddc0e7085d254b42a0d82a789491b8cb",
      "summary_schema_version": "r14_summary_v1",
      "status": "PASS_R14_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
      "completed_gates": [
        "resolution_freeze",
        "structural_input",
        "fixture_identifiability",
        "transport_competence",
        "anti_equivalence",
        "mediator_recovery",
        "fair_baseline",
        "exact64_bridge"
      ],
      "not_run_gates": [
        "independent_reproduction"
      ],
      "eligible_engineering_evidence": true,
      "scientific_method_evidence": false
    }
  },
  "registered_r16_failed_audit_forensic_evidence": {
    "source_protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R16_2026-07-23.md",
      "protocol_sha256": "460ee47547aa49837a748961063029d14c803c346d19316beda7cdda607f45ca",
      "registry_sha256": "394f202f5694d0b4f56d741d30584515b877a67459f977853154d34f559f17c9"
    },
    "source_audit_relative_path": "artifacts/calibration/.r16_phase_authorizations/r14_registered_local_postrun_audit.json",
    "disposition": "immutable_forensic_evidence_only_not_an_r18_authorization_prerequisite",
    "retained_without_rewrite": true,
    "eligible_engineering_evidence": false,
    "scientific_method_evidence": false
  },
  "registered_r17_incomplete_freeze_forensic_evidence": {
    "source_protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R17_2026-07-23.md",
      "protocol_sha256": "d725c9b4bb8fa3217a5057c8e6b306230072bfe3afc1ee712c00a21ab874d6b9",
      "registry_sha256": "9bbba44abd6587a13c3298f3348650737066d370b6f7937a5847443f6b9a7fa3"
    },
    "observed_freeze_record_schema": "r17_freeze_record_v1",
    "disposition": "immutable_forensic_evidence_only_not_an_r18_authorization_prerequisite",
    "failure_class": "FAIL_R17_INCOMPLETE_FREEZE_RECORD",
    "retained_without_rewrite": true,
    "eligible_engineering_evidence": false,
    "scientific_method_evidence": false
  },
  "registered_r18_prefinalization_runner_forensic_evidence": {
    "source_protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R18_2026-07-23.md",
      "protocol_sha256": "742c3b03e0c3be0f9aee32a9c233d61cd4a0c7140ea0fb160f41e1fa3d754717",
      "registry_sha256": "00ff74b393984abaa9a32213b99ad8ac0d797fb893afc433cb8a82fa77cd6ed8",
      "registry_sha256_semantics": "r18_full_canonical_registry"
    },
    "observed_freeze_record_schema": "r18_freeze_record_v1",
    "observed_implementation_schema_versions": {
      "resolver": "r17_resolver_v1",
      "summary": "r17_summary_v1",
      "runtime_environment": "r6_runtime_environment_v1",
      "source_manifest": "r17_closed_source_manifest_v1",
      "result": "r6.result.v1",
      "initialization": "r17_initialization_evidence_v1",
      "structural_microcases": "visualvit.r6-structural-audits.v3",
      "counterfactual": "visualvit.r6_counterfactual_audits.v1",
      "independent_validator": "visualvit.r6-validation.v4",
      "data_access_ledger": "r6_split_access_ledger_v1",
      "exact64_ledger": "r6_exact64_call_ledger_v1",
      "reproduction": "r17_reproduction_certificate_v1",
      "failure": "r17_atomic_failure_v1",
      "freeze_record": "r18_freeze_record_v1",
      "dryrun_postrun_audit": "r17_dryrun_postrun_audit_v1",
      "smoke_authorization": "r17_smoke_authorization_certificate_v1",
      "smoke_postrun_audit": "r17_smoke_postrun_audit_v1",
      "registered_authorization": "r17_registered_authorization_certificate_v1"
    },
    "disposition": "immutable_forensic_evidence_only_not_an_r19_authorization_prerequisite",
    "failure_class": "FAIL_R18_RUNNER_NOT_NATIVE_R18_BEFORE_FINALIZATION",
    "retained_without_rewrite": true,
    "eligible_engineering_evidence": false,
    "scientific_method_evidence": false
  },
  "r22_pre_finalization_runner_contract": {
    "required_before_finalizer_import_or_implementation_observation": true,
    "runner_must_natively_load_protocol_relative_path": "refine-logs/CALIBRATION_PROTOCOL_R22_2026-07-23.md",
    "runner_must_natively_expose_protocol_id": "CAPES_CI_QPTM_R22_2026_07_23",
    "runner_must_natively_expose_registry_object": true,
    "runner_must_natively_expose_r22_schema_and_run_namespaces": true,
    "runner_must_natively_expose_source_manifest_authority_contract": true,
    "finalizer_retargeting_or_monkeypatching_runner_authority_forbidden": true,
    "finalizer_may_only_observe_and_validate_native_runner_state": true
  },
  "registered_r19_passing_audit_and_preissued_child_certificates_forensic_evidence": {
    "source_protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R19_2026-07-23.md",
      "protocol_sha256": "e5ae71ff87e8d087b34b80cd8c8ead8c6f912ec4715089924d2ee85db70fc8eb",
      "registry_sha256": "f7ff8d4ca81f98ab1fbdc134172af4df7f7e4855728715c429fa923ee7922f32",
      "registry_sha256_semantics": "r19_full_canonical_registry"
    },
    "artifacts": {
      "registered_postrun_audit": {
        "path": "artifacts/calibration/.r19_phase_authorizations/r14_registered_local_postrun_audit.json",
        "file_sha256": "e7501c83700181f965d032c7900221b2083646f35ec9f050c8efb3f371feaae9",
        "self_hash_field": "audit_sha256",
        "self_sha256": "4409467202e17bbbefe891fd353a87017b3916b44500bd2764942825ccc433f1",
        "verdict": "PASS_R19_REGISTERED_POSTRUN_AUDIT",
        "retained_without_rewrite": true,
        "eligible_r20_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "preissued_process_a_authorization": {
        "path": "artifacts/calibration/.r19_phase_authorizations/reproduction_process_a_authorization.json",
        "file_sha256": "00f4cd769ceb2e5fbffa7ec40707d25557ac35a0b565c946e8cc2e2f93497c46",
        "self_hash_field": "certificate_self_sha256",
        "self_sha256": "6501085786a2aafc6b093c170a3d56a531b1425a39bac0044909ab94b38a5faa",
        "certificate_id": "17cdca74-978c-48b4-a395-a4ae25d78a66",
        "target_child_leaf": "process_a",
        "retained_without_rewrite": true,
        "eligible_r20_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "preissued_process_b_authorization": {
        "path": "artifacts/calibration/.r19_phase_authorizations/reproduction_process_b_authorization.json",
        "file_sha256": "4a1575a2d1b2738ee42006ba93e786dc6ce2f37f001f27868f4afe3c91eb7fc0",
        "self_hash_field": "certificate_self_sha256",
        "self_sha256": "b4ede51dbd8e8f27def1229616a4d36da8337a49add3a9123869dfcc500e6f48",
        "certificate_id": "d4aa8f39-85ef-4ec5-8258-c3586e87f462",
        "target_child_leaf": "process_b",
        "retained_without_rewrite": true,
        "eligible_r20_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      }
    },
    "disposition": "immutable_ineligible_forensic_evidence_only_not_an_r20_authorization_prerequisite_or_reusable_authority",
    "failure_class": "INELIGIBLE_R19_CHILD_CERTIFICATES_PREISSUED_OUTSIDE_THE_R20_LAUNCHER_OWNED_ISSUER_TRANSACTION",
    "retained_without_rewrite": true,
    "eligible_engineering_evidence": false,
    "scientific_method_evidence": false,
    "passing_r19_audit_finding_retained": true,
    "preissued_r19_child_certificate_pair_retained": true,
    "r19_artifacts_authorize_r20": false
  },
  "r22_launcher_owned_issuer_transaction_contract": {
    "transaction_owner": "scripts/run_query_anchor_r4_reproduction.py",
    "issuer_invocation_count_exact": 1,
    "synchronous": true,
    "retry_allowed": false,
    "preissued_r22_audit_allowed": false,
    "preissued_r22_child_certificates_allowed": false,
    "required_precheck_order": [
      "target_output_parent_absent",
      "r22_authority_namespace_absent",
      "r22_registered_audit_absent",
      "r22_process_a_certificate_absent",
      "r22_process_b_certificate_absent"
    ],
    "issuer_invocation_after_all_prechecks": true,
    "issuer_success_and_two_certificate_reopen_before_parent_creation": true,
    "partial_issuance_or_nonzero_exit_is_terminal_no_retry": true,
    "r20_authority_namespace_is_forensic_only_and_never_read_as_r22_authority": true,
    "r21_authority_namespace_is_forensic_only_and_never_read_as_r22_authority": true
  },
  "registered_r20_materializer_key_failure_forensic_evidence": {
    "source_protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R20_2026-07-23.md",
      "protocol_sha256": "db7582b7fc25b8edfc8d693c046e62a09a014a31be54d7b3ed00df616ebc006d",
      "registry_sha256": "2a272c1dc90a22e2118f84cc6b3606709570452181fb9d785594940a37e1df6b",
      "registry_sha256_semantics": "r20_full_canonical_registry"
    },
    "artifacts": {
      "registered_postrun_audit": {
        "path": "artifacts/calibration/.r20_phase_authorizations/r14_registered_local_postrun_audit.json",
        "file_sha256": "e9085f1f3bc439a1d3182595b376caae3288ab67931730abf61f588822269b6a",
        "expected_json_fields": {
          "audit_sha256": "71c15b668295d493089c6197daf0f6a0aeb43793cbb404340428e6698beffd6d",
          "verdict": "PASS_R20_REGISTERED_POSTRUN_AUDIT"
        },
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_authorization": {
        "path": "artifacts/calibration/.r20_phase_authorizations/reproduction_process_a_authorization.json",
        "file_sha256": "3115d3e76f47803582b5643488a796b73fefddf64f3d2716a02353aa4945459d",
        "expected_json_fields": {
          "certificate_self_sha256": "d98ef3e1c4ab806853b2f5000779efa46e3067b7c287afde0bebc3096290810c",
          "certificate_id": "54f6ad47-9273-4614-8839-f968900f7a2f",
          "target_child_leaf": "process_a"
        },
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_b_authorization": {
        "path": "artifacts/calibration/.r20_phase_authorizations/reproduction_process_b_authorization.json",
        "file_sha256": "14efcfc8d61a8ea272f7cc5fba9c11737bc595c784d20837cc1ca5001fdd4bc4",
        "expected_json_fields": {
          "certificate_self_sha256": "24979b3e52e850e136a7dfed737ebcc90f4be630ac97b0748f57ceb9eedc11ac",
          "certificate_id": "01919d27-cfb3-440c-a00f-38706136019d",
          "target_child_leaf": "process_b"
        },
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_claim": {
        "path": "artifacts/calibration/.r20_phase_authorizations/claims/reproduction_process_a_authorization.54f6ad47-9273-4614-8839-f968900f7a2f.d64bd7a8dd0bb88838906b28d638a4016972a516a879b82de3170040cc6a7fc3.process_a.claim.json",
        "file_sha256": "e51ba9ee0b742c23f08e2707c3815cbc0dbbbbd5a9b3f2d7f7c0a0b5c7eb0613",
        "expected_json_fields": {
          "claim_self_sha256": "7469f571013e1cb8f01c244478783b4576ca321b7b4201b6ed2f1336aa4b9e65",
          "certificate_id": "54f6ad47-9273-4614-8839-f968900f7a2f",
          "target_child_leaf": "process_a"
        },
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "launcher_failure": {
        "path": "artifacts/calibration/capes_ci_qptm_r20_reproduction_local_20260723_v1/failure.json",
        "file_sha256": "6653d1b50e10f5fcd61daec8b499b453679141021281e4ab21c1c8b3f8b28714",
        "expected_json_fields": {
          "status": "TECHNICAL_FAILURE_R20_REPRODUCTION_LAUNCHER",
          "stage": "child_summary_read"
        },
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_failure": {
        "path": "artifacts/calibration/capes_ci_qptm_r20_reproduction_local_20260723_v1/process_a/failure.json",
        "file_sha256": "8803b7cbeec54a97fa36cbc35ed8a85cece485a395983c4b04a5699e61d7aef4",
        "expected_json_fields": {
          "status": "TECHNICAL_FAILURE_R20_UNHANDLED_EXCEPTION",
          "stage": "gate_execution"
        },
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_stdout": {
        "path": "artifacts/calibration/capes_ci_qptm_r20_reproduction_local_20260723_v1/process_a.stdout.log",
        "file_sha256": "af27a4718778879e247a886307f5d442759801d94082634c330018876b24740f",
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_stderr": {
        "path": "artifacts/calibration/capes_ci_qptm_r20_reproduction_local_20260723_v1/process_a.stderr.log",
        "file_sha256": "3aa6a1f64bae9b079186d6287083eadc1e96421e3c8c7a34fbba133d0d3721fd",
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "scheduled_launcher_result": {
        "path": "artifacts/calibration/r20_launcher_logs/launcher_process_result.json",
        "file_sha256": "7f3c20f5eaa1a52c7b2ee5a24ed579826ff25b49573e48067c4e3c15a1945977",
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "scheduled_launcher_log": {
        "path": "artifacts/calibration/r20_launcher_logs/launcher_stdout_stderr.log",
        "file_sha256": "d0c3cdb3c120c3f0f2b3db79163cc3ca1d58ba09c30c3d20550206b5b40d8f7b",
        "retained_without_rewrite": true,
        "eligible_r21_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      }
    },
    "disposition": "immutable_ineligible_forensic_evidence_only_not_an_r21_authorization_prerequisite_or_reusable_authority",
    "failure_class": "R20_REPRODUCTION_MATERIALIZER_KEY_CONSISTENCY_TECHNICAL_FAILURE",
    "retained_without_rewrite": true,
    "eligible_engineering_evidence": false,
    "scientific_method_evidence": false,
    "r20_launcher_owned_issuer_transaction_completed": true,
    "r20_process_a_claim_retained": true,
    "r20_process_a_summary_publication_failed": true,
    "r20_process_b_never_launched": true,
    "r20_artifacts_authorize_r21": false,
    "r20_artifacts_are_r21_prerequisites": false,
    "pins_are_registry_metadata_only": true,
    "live_path_existence_or_hash_revalidation_required_for_r21_freeze": false,
    "sole_r21_freeze_base_prerequisite": "frozen_r20_protocol_bytes_and_full_canonical_registry"
  },
  "materializer_id_consistency_contract": {
    "scope": "reproduction_authorization_materializer_identity",
    "canonical_registry_key": "issuing_materializer_id",
    "canonical_registry_pointer": "/phase_authorization_contract/reproduction_authorization/issuing_materializer_id",
    "canonical_value": "registered_reproduction_authorizer",
    "required_consumers": [
      "issuer_materializer",
      "launcher_reopen",
      "runner_preclaim",
      "runner_summary_receipt",
      "runner_prepublication"
    ],
    "consumer_value_rule": "every_required_consumer_must_read_the_canonical_registry_key_directly_and_compare_exactly_against_materializer_provenance_materializer_id",
    "alias_keys_forbidden": [
      "issuer_materializer_id"
    ],
    "alias_fallback_forbidden": true,
    "missing_or_nonexact_canonical_key_is_terminal": true,
    "scientific_contract_delta": false
  },
  "registered_r21_source_manifest_failure_forensic_evidence": {
    "source_protocol": {
      "path": "refine-logs/CALIBRATION_PROTOCOL_R21_2026-07-23.md",
      "protocol_sha256": "693e9e887b9912fa00b532535be95e34abe41b0d15930505a457f8a781b92f1d",
      "registry_sha256": "a3735022a60575477800f0395f83dc7809a11c26a59dd41a36d363939e70f04f",
      "registry_sha256_semantics": "r21_full_canonical_registry"
    },
    "artifacts": {
      "registered_postrun_audit": {
        "path": "artifacts/calibration/.r21_phase_authorizations/r14_registered_local_postrun_audit.json",
        "file_sha256": "7f6970d221a4db2deff17e1b4532ae856c21bc7039a86a27a561dafcfd0b5412",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_authorization": {
        "path": "artifacts/calibration/.r21_phase_authorizations/reproduction_process_a_authorization.json",
        "file_sha256": "021f178fbecab1eef5f59cfc6436b635a7182cf73e53f1fd3f6d4ea1d3bccc07",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_b_authorization": {
        "path": "artifacts/calibration/.r21_phase_authorizations/reproduction_process_b_authorization.json",
        "file_sha256": "4d859be158f903fa4a7fbf87f4025308f4fda3c5f09b8395e368981f46cd6102",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_claim": {
        "path": "artifacts/calibration/.r21_phase_authorizations/claims/reproduction_process_a_authorization.14cd55e8-1d7d-4f97-b246-9c1f8ccd3ef2.c68264fb4e3ca377fda4cdeda5ba8d77ffae2871d87241c7f4232c9a6609dce1.process_a.claim.json",
        "file_sha256": "96a1d9c9b678f3c392c420ba5bb9fd0f96e4044db6b81d263ba4f6e69df705d0",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_summary": {
        "path": "artifacts/calibration/capes_ci_qptm_r21_reproduction_local_20260723_v1/process_a/summary.json",
        "file_sha256": "9d93e5050987e4ed58ef93db02fbcff325e93cba780a19a7fd7b6b4f33d8afd6",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "launcher_failure": {
        "path": "artifacts/calibration/capes_ci_qptm_r21_reproduction_local_20260723_v1/failure.json",
        "file_sha256": "7e7e038ed4206ad705fac093c0c7d999daf6c1a3780c370935775a4f551fc627",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_stdout": {
        "path": "artifacts/calibration/capes_ci_qptm_r21_reproduction_local_20260723_v1/process_a.stdout.log",
        "file_sha256": "72757edd78d0a3b8ed1059d92c38f31d4122636d6dc64d5602347f28d6285393",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "process_a_stderr": {
        "path": "artifacts/calibration/capes_ci_qptm_r21_reproduction_local_20260723_v1/process_a.stderr.log",
        "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "scheduled_launcher_result": {
        "path": "artifacts/calibration/r21_launcher_logs/launcher_process_result.json",
        "file_sha256": "a645bf2feba97705e83a9bce97aaa1d9d463beb17ebfbb1be17406832a9afb2a",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      },
      "scheduled_launcher_log": {
        "path": "artifacts/calibration/r21_launcher_logs/launcher_stdout_stderr.log",
        "file_sha256": "57c8286bbed45ea4548c00f6a4d6c87485d81fd697678322f144493ef2496d5a",
        "retained_without_rewrite": true,
        "eligible_r22_authorization": false,
        "eligible_engineering_evidence": false,
        "scientific_method_evidence": false
      }
    },
    "failure_class": "R21_CROSS_PROCESS_OBSERVED_IMPORTS_CONTAMINATED_SOURCE_AUTHORITY",
    "disposition": "immutable_ineligible_forensic_metadata_only_not_an_r22_authorization_prerequisite_or_reusable_authority",
    "r21_process_a_returncode_zero": true,
    "r21_process_a_gates_0_to_7_passed": true,
    "r21_process_a_strict_summary_validation_passed": true,
    "sole_failed_child_eligibility_check": "source_manifest_authority_exact",
    "r21_process_b_never_launched": true,
    "r21_artifacts_authorize_r22": false,
    "r21_artifacts_are_r22_prerequisites": false,
    "pins_are_registry_metadata_only": true,
    "live_path_existence_or_hash_revalidation_required_for_r22_freeze": false,
    "sole_r22_freeze_base_prerequisite": "frozen_r21_protocol_bytes_and_full_canonical_registry",
    "scientific_method_evidence": false
  },
  "r22_finalization_contract": {
    "candidate_authority_state": "PRE_FREEZE_AWAITING_R22_IMPLEMENTATION_HASHES",
    "frozen_authority_state": "FROZEN_BEFORE_R22_REPRODUCTION",
    "candidate_status": "PRE_FREEZE_AWAITING_R22_IMPLEMENTATION_HASHES",
    "frozen_status": "FROZEN_BEFORE_R22_REPRODUCTION",
    "freeze_boolean_json_pointers": [
      "/freeze_requirements/implementation_hashes_frozen",
      "/freeze_requirements/dry_run_authorized"
    ],
    "additional_frozen_paths": [
      "/freeze_requirements/external_materializer_hashes_prebound_and_live_verified",
      "/phase_authorization_contract/external_materializers/registered_reproduction_authorizer/sha256",
      "/implementation_observation_expected",
      "/freeze_record"
    ],
    "freeze_record_semantics": "r22_complete_nonself_final_protocol_projection_contract_v1",
    "protocol_candidate_sha256_semantics": "sha256_of_exact_final_frozen_protocol_utf8_bytes_with_the_first_registry_freeze_record_replaced_by_json_null_and_no_other_byte_changes",
    "finalizer_projection_order": [
      "construct_final_frozen_prose",
      "construct_final_registry_state_with_freeze_record_json_null",
      "hash_exact_utf8_protocol_projection_bytes",
      "insert_complete_freeze_record_without_other_byte_changes"
    ],
    "canonical_registry_sha256_semantics": "sha256_over_canonical_registry_after_removing_only_top_level_freeze_record",
    "closed_manifest_sha256_semantics": "sha256_over_freeze_nonprotocol_allowlist_and_file_hash_projection",
    "certificate_source_manifest_authority_sha256_semantics": "runner_source_manifest_authority_sha256_over_exact_schema_allowlist_files_including_final_protocol_excluding_process_local_observation",
    "source_manifest_observation_semantics": "process_local_import_subset_diagnostic_excluded_from_authority",
    "closed_manifest_sha256_must_not_equal_or_substitute_for_certificate_source_manifest_authority_sha256": true,
    "native_runner_precondition_ref": "/r22_pre_finalization_runner_contract"
  }
}
```

## 3. Frozen execution boundary

R22 is PRE_FREEZE. Source authority consists only of its registered schema,
closed allowlist, and exact live file hashes. `observed_workspace_imports` is a
process-local closed-world diagnostic: it must be a subset of the allowlist but
is excluded from the source-authority hash and is never compared for equality
across launcher, issuer, runner, or child processes.

R22 is frozen before independent reproduction: native implementation and external-materializer hashes are frozen, but freeze alone authorizes no execution. Independent reproduction remains gated by the launcher's synchronous exactly-once no-retry issuer transaction, fresh R22 audit, two fresh R22 child certificates, claims, and runner verification. Dry-run, smoke, registered-local, GPU, Slurm/4161, download, formal-data, and formal-test paths remain unauthorized.

## 4. Scientific invariance and forensic boundary

This is an administrative integrity delta only. R22 changes no scientific
method, architecture, objective, fixture, threshold, seed, split, optimizer,
registered step count, gate order, survival logic, formal boundary, claim flag,
data contract, or two-child routing. R21 process A completed Gates 0 through 7
and strict summary validation, but the parent failed only because process-local
import observation contaminated the old cross-process source hash. Every R21
runtime artifact remains immutable, ineligible forensic metadata only and
cannot authorize or serve as a prerequisite for R22.

The frozen R14 v5 validator bundle and every R14 pin remain unchanged. Formal
data is HOLD, formal test is SEALED, downloads and GPU/Slurm execution remain
unauthorized, and retained allocation `4161 / tpami / gpu01` must not be
cancelled or released.

## 5. R22 independent-reproduction boundary

R22 registers fresh `.r22_phase_authorizations`, R22 audit, child-certificate,
claim, failure, and reproduction-root paths only. The launcher-owned
synchronous exactly-once no-retry transaction is the sole issuer route. A fresh
process A must be fully eligible before fresh sequential process B may start.
