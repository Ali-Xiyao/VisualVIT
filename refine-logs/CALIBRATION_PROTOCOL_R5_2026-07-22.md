# CAPES-CI QPTM R5 Preregistered Synthetic Engineering Protocol

Status: `FROZEN_BEFORE_R5_DRY_RUN`  
Date: 2026-07-22  
Protocol ID: `CAPES_CI_QPTM_R5_2026_07_22`  
Evidence class: `E1_SYNTHETIC_ENGINEERING_NONCONFIRMATORY`

## 1. Authority and supersession

This document is the sole protocol authority for the next QPTM synthetic
engineering run. The R3 registered result remains an immutable
`STOP_LEARNED_RECOVERY` negative result. R4 development established that the
new fixture and runner were executable, but an R4 dry-run had already occurred
before subsequent source and protocol corrections. Therefore every artifact
whose run directory or protocol identifier begins with R4, including
`r4_runner_final_dryrun_20260722`,
`r4_runner_final_smoke_seed17_20260722_v2`, and
`r4_runner_final_smoke_seed17_20260722_v3`, is **superseded development
evidence**. Those artifacts must remain immutable and visible; none is eligible
for an R5 gate, aggregate, reproduction, or scientific claim.

R5 tests one proposition only:

> A query-independent, two-sided partial-transport owner can recover one
> persistent correspondence plan for an image pair, after which a query may
> gate only the transported relation/change representation used by a
> fixed-budget mediator.

The potential contribution is this query-sealed transport-to-mediator
interface and its intervention-ready fixed-budget representation. Cosine
similarity, Hungarian assignment, Sinkhorn projection, partial transport,
dustbins, null rejection, and slot/token allocation are established machinery
and are not claimed as novel.

R5 makes no claim for a contextual edge residual. The registered scorer has
only a bounded scalar monotone calibration of a weighted cosine utility; it
does not inspect neighborhoods, context statistics, queries, states, or
labels. A genuinely contextual, permutation-equivariant residual is a possible
future method version and is outside R5.

## 2. Machine-readable frozen registry

The following JSON object is normative. Decimal values are interpreted as
IEEE-754 binary64 configuration values; model parameters are stored as
IEEE-754 binary32. A runner/config disagreement is a resolution-gate failure.

```json
{
  "protocol_id": "CAPES_CI_QPTM_R5_2026_07_22",
  "evidence_class": "E1_SYNTHETIC_ENGINEERING_NONCONFIRMATORY",
  "resolver_schema_version": "r5_resolver_v1",
  "summary_schema_version": "r5_summary_v1",
  "feature_dim": 18,
  "channels": {
    "query_marker": [0, 1],
    "state": [1, 2],
    "identity_views": [[2, 8], [8, 14]],
    "prior_death_support": [14, 16],
    "current_birth_support": [16, 18]
  },
  "strata": ["clean", "challenge"],
  "splits": ["train", "inner_development", "development"],
  "counterbalance_groups": {
    "train": 4,
    "inner_development": 2,
    "development": 6
  },
  "clean_split_seeds": {
    "train": 96501,
    "inner_development": 97501,
    "development": 98501
  },
  "challenge_split_seeds": {
    "train": 93501,
    "inner_development": 94501,
    "development": 95501
  },
  "audit_fixture_seeds": {
    "clean_fixture_development": 96531,
    "challenge_fixture_development": 93531
  },
  "fixture_hash_algorithm": "visualvit.calibration_r5_visible_hidden_and_full_fixture_sha256",
  "fixture_hashes": {
    "clean": {
      "train_visible": "166baa33ee89790bce061ee739f1d9cc404e4b4b8ce2f53ffdf178d4c505e23c",
      "train_oracle": "a2c55268c1eb3c9009938b1cac554c1cd53ff05a144609a72f7db964c30c7a9a",
      "inner_development_visible": "bf7a3b3952b4e032fa7e435352c7ef1ce2b2cf57c1a8f19dc69d32d6017272fc",
      "inner_development_oracle": "33a4bbfc9d774b0a6e9c46253e53ae615dc8d8c874cdcf1cfaecab5c955f077a",
      "development_visible": "2db8735686044e8d1debdb559e60e27cce03a6da3640438117aa7c36744a29a9",
      "development_oracle": "afb360beebd77813649534ab6d19341bff6894ad29156ed04be9329e5751bd1d",
      "fixture_development_visible": "8bd53f61506ca8eeffef444f1079a5d14edca42f8f2d59d07ec8bdde0b8b0690",
      "fixture_development_oracle": "d9c6a3d86ddecaf52c53ee07007a79d06eac0a60be451cb9103568ea139e82d0"
    },
    "challenge": {
      "train_visible": "557a2df32d298d82432b6b73424ef9ccadfadfbc420e11b2b98c8e3515210d9e",
      "train_oracle": "725ef95f8e3c419589d86348b9d6aafff15e364f23e87e885efc43fcc8f95e91",
      "train_full": "5f49e85bcb3f515fe722779b6c6cbc4d5667b3f94bfd9af8bc3b744a61cb3872",
      "inner_development_visible": "b2dfecd1741bc2f4bea15110ed6584b0d6e824b9d3b1fd14b3786220e8cb587e",
      "inner_development_oracle": "ae9483a6668c7384d66903b6bafea5cd79c7a0e72a651a08a7d78135db993c83",
      "inner_development_full": "b60bc5d744ac1f41a943843ac381f93c26b9f783003d0d0d32e8b38110c8f75e",
      "development_visible": "10dfdd1f45ee01ef6426a1a5cc6e1b4893307d814c669e102baf012cf398d332",
      "development_oracle": "df4693d9a3477f02692e39fe63d00756bef8fd70d10ec1818b8abd3ed42103a0",
      "development_full": "0f199b17048345dc308268c60685248105aa9da06860717adfaa7acb895e1c44",
      "fixture_development_visible": "a1960c60dc2a5ea35d52d0602731aea8826aece41644758e00a6e9ae9e46e19a",
      "fixture_development_oracle": "02e02f4c9b4dbbbf4360162315a3e438376aeab043b9e1638121b65224515c9c",
      "fixture_development_full": "dc9b70d07aae6c8e92e8d40b199616566b723b82ee490ea43128f9429ba91fe1"
    }
  },
  "enumerator_authority": {
    "path": "src/visualvit/calibration_r5.py",
    "symbol": "enumerate_r5_clean_assignment_certificate",
    "source_sha256": "4d5f6569ae349c5fd99563f287fa9cc4c375484aa81a8fad149447bee8326537",
    "dependency_path": "src/visualvit/calibration_r4.py",
    "dependency_sha256": "f6bf381d1db21a0eb8f943ec23abb8fbb1cef2a83a65863be90fbd912ccf4731",
    "test_path": "tests/test_calibration_r5.py",
    "test_sha256": "28fb9e90921e36c8cfc6795c4de12b2f125800369956cdf9b0f98e483f2feaa6",
    "gate_spec_path": "reports/r5_runner_gate_spec_2026-07-22.md",
    "gate_spec_sha256": "9ee58dd2053816d216bc5ed8d339fb4bb4488c092fccd090cd05bcbccd385715",
    "canonical_certificate_sha256": "51d3374f0b2c9b5376f7f2f355da0fb158797f1ca1a5582481d83a550bdaddde",
    "partial_assignments_enumerated_per_anatomy": 130922,
    "analytic_minimum_gap_before_numerical_deduction": 0.7847681168808847,
    "float32_cosine_error_cap_per_edge": 0.0000005,
    "float32_worst_case_gap_deduction": 0.00000663,
    "registered_minimum_robust_gap": 0.7847614868808847,
    "challenge_view1_minimum_best_vs_second_gap_across_splits": 0.36974024772644043,
    "enumeration_domain": {
      "view_weights": "complete_two_view_probability_simplex",
      "null_utility_effective_interval": [-0.10, 0.10],
      "scalar_monotone_effective_cap": 0.02,
      "anatomy_constrained": true
    },
    "design_witness": {
      "view_weights": [0.95, 0.05],
      "scalar_monotone_coefficient_effective": 0.0,
      "death_utility_effective": 0.05,
      "birth_utility_effective": 0.05,
      "death_utility_raw": 0.5493061443340549,
      "birth_utility_raw": 0.5493061443340549,
      "role": "feasibility_witness_not_threshold_source"
    }
  },
  "trainable_seeds": [17, 29, 43],
  "registered_derangement_seeds": [81001, 81002, 81003],
  "registered_steps_per_stage": 500,
  "utility": {
    "view_weight_parameterization": "softmax_two_logits",
    "scalar_monotone_cap": 0.02,
    "scalar_monotone_formula": "0.02*tanh(a)*tanh(weighted_cosine)",
    "null_utility_cap": 0.10,
    "death_utility_formula": "0.10*tanh(d_raw)",
    "birth_utility_formula": "0.10*tanh(b_raw)",
    "anatomy_constrained": true
  },
  "initialization": {
    "distribution": "Normal(0,0.01)",
    "mean": 0.0,
    "standard_deviation": 0.01,
    "generator": "torch.Generator(device=cpu).manual_seed(trainable_seed)",
    "generation_runtime": "torch_2.5.1+cu121",
    "generation_expression": "0.01*torch.randn(5,generator=cpu_generator,dtype=torch.float32)",
    "runtime_rule": "load_frozen_literals_do_not_redraw",
    "hash_rule": "sha256_of_concatenated_little_endian_float32_bytes_in_declared_order",
    "absolute_literal_bound": 0.02,
    "flattened_parameter_order": [
      "residual_coefficient",
      "view_weight_logit_0",
      "view_weight_logit_1",
      "prior_null_utility_raw",
      "current_null_utility_raw"
    ],
    "literal_values": {
      "17": [-0.014135131612420082, 0.002336307428777218, 0.0003403318114578724, 0.003499172627925873, -0.00014521554112434387],
      "29": [0.011473960243165493, -0.0014166508335620165, 0.0047425320371985435, 0.0008759791380725801, 0.006843280512839556],
      "43": [-0.006484010722488165, -0.007058414164930582, 0.0064321840181946754, 0.014787990599870682, 0.011918498203158379]
    },
    "literal_vector_sha256": {
      "17": "f1da44f311610a3f292baa4c8f0ff03ee6b7881d69872b2b3243434694cc7190",
      "29": "2ecdc2bfe052fac2b251985056ec41ac1da6ff4e5b9e5538afc316a9ab2a913a",
      "43": "a924c851240c484f9038325d4a3477a1d4b4686020b54e5a3de1cad2b5c87ba3"
    },
    "per_parameter_tensor_sha256": {
      "17": {
        "residual_coefficient": "2ae3c5d18e12adcfcd395b6028990450742340e965216d8bb1cd40d5b7fdfeb3",
        "view_weight_logits": "e1aa8f389c1bf95d43a6e0e452052c0e601c1d775c0cce73324ad74ee2ab266b",
        "prior_null_utility_raw": "633739f03430d7bc2addce78a99b8c7f73cf6b79564b70927b938beff2c2dbe2",
        "current_null_utility_raw": "712eb1187e2cba79a32ecdf6abb3b400fd891b91f4bcb04cc9b977511e04fca4"
      },
      "29": {
        "residual_coefficient": "5f4c1f4bfb5dd803d44a870e33eb260b8a2fc7b8f4facb0c53b45937e7da54c4",
        "view_weight_logits": "4e8cd7f7a03309c77003f4f99bd7cc4dae56a93074023fb9f2807379deeb41e5",
        "prior_null_utility_raw": "74c8421ed9d7b3949bd65e3019e412b8119a811cc25dce120d18c4dc5b042572",
        "current_null_utility_raw": "af968c31340b38b8f568b5959498daa72d6647f9319bef1fe52c7ebeb1da4f87"
      },
      "43": {
        "residual_coefficient": "94bdd0229bac7bcbcc403c9abe6be51cd8a951a9faded3c0717ed9774d4104df",
        "view_weight_logits": "935b5ca269a2f878637eccf95e3f239a36f5146a8e3fb75c7a2c225e8c332577",
        "prior_null_utility_raw": "b5e7dfd9ba3aa983536dbc168031f02d153d66f5c1e14ce5a7e0ec1bb81fd25d",
        "current_null_utility_raw": "5f94eb275057a7c71a719bc966a052ba47451812e7d2fb2a5a1dd431532e3325"
      }
    }
  },
  "soft_solver": {
    "name": "log_domain_augmented_sinkhorn",
    "temperature": 0.05,
    "iterations": 256,
    "feasibility_tolerance": 0.00001
  },
  "hard_solver": {
    "name": "augmented_hungarian_same_utility",
    "tie_policy": "lexicographically_smallest_augmented_assignment",
    "reject_policy": "real-real edge is rejected when the globally optimal augmented assignment uses its death and birth alternatives"
  },
  "transport_training": {
    "loss": "equal_mean_over_strata_full_oracle_augmented_transport_nll",
    "optimizer": "AdamW",
    "learning_rate": 0.02,
    "weight_decay": 0.0,
    "gradient_clip_l2": 1.0,
    "checkpoint": "final_step_only",
    "query_label_gradients": false
  },
  "mediator_training": {
    "loss": "equal_mean_over_strata_label_cross_entropy",
    "optimizer": "AdamW",
    "learning_rate": 0.02,
    "weight_decay": 0.0,
    "gradient_clip_l2": 1.0,
    "checkpoint": "final_step_only",
    "matcher_frozen": true
  },
  "matched_local_baseline": {
    "name": "TrainableLocalIndependentMatcher",
    "parameterization": "same_five_utility_parameters_and_literal_initialization_as_main",
    "allocator": "independent_prior_row_softmax_over_compatible_real_edges_plus_private_death",
    "column_normalization": false,
    "column_capacity_competition": false,
    "duplicate_current_allowed": true,
    "real_assignment_estimand": "row_top1_accuracy",
    "row_top1_tie_policy": "a_row_is_correct_only_when_the_oracle_target_is_the_unique_maximizer_non_unique_maxima_score_zero",
    "hard_matchplan_claim": false,
    "birth_weight_formula": "sigmoid(u_birth/temperature)*product_over_compatible_prior_rows(1-p_row_real_ij)",
    "birth_hard_diagnostic_threshold": 0.5,
    "loss": "mean_oracle_row_nll_plus_mean_oracle_birth_binary_cross_entropy",
    "relation_adapter": "independent_fixed_budget_local_relation_token_adapter",
    "relation_adapter_calls_matchplan_validate": false,
    "forbidden_operations": [
      "column_softmax",
      "column_normalization",
      "mutual_argmax",
      "greedy_one_to_one",
      "hungarian",
      "sinkhorn",
      "topk_across_prior_rows"
    ],
    "optimizer": "AdamW",
    "learning_rate": 0.02,
    "weight_decay": 0.0,
    "gradient_clip_l2": 1.0,
    "steps": 500,
    "checkpoint": "final_step_only"
  },
  "common_oracle_frozen_readout": {
    "fit_scope": "registered_train_only",
    "fit_count_per_seed": 1,
    "post_freeze_update_count": 0,
    "training_strata_order": ["clean", "challenge"],
    "loss": "equal_mean_over_strata_label_cross_entropy_on_oracle_plans",
    "optimizer": "AdamW",
    "learning_rate": 0.02,
    "weight_decay": 0.0,
    "gradient_clip_l2": 1.0,
    "steps": 500,
    "checkpoint": "final_step_only",
    "query_raw_dim": 6,
    "query_hidden_size": 8,
    "projector_initialization_seed": "trainable_seed",
    "frozen_adapter_seed": 91001,
    "comparison_method_order": [
      "oracle",
      "main",
      "local_independent",
      "fixed_hungarian",
      "fixed_sinkhorn",
      "B4b_oracle",
      "B4a_deranged_81001",
      "B4a_deranged_81002",
      "B4a_deranged_81003"
    ],
    "one_state_hash_per_seed_shared_by_every_method": true,
    "main_mediator_result_key": "main_mediator_diagnostic_disjoint_from_common_readout"
  },
  "thresholds": {
    "trained_no_pair_axis_macro_f1_max": 0.45,
    "challenge_per_view_row_argmax_target_state_development_accuracy_max": 0.3333333333333333,
    "challenge_per_view_row_argmax_target_state_development_macro_f1_max": 0.3333333333333333,
    "challenge_combined_view_row_argmax_target_state_development_accuracy_max": 0.3333333333333333,
    "challenge_combined_view_row_argmax_target_state_development_macro_f1_max": 0.3333333333333333,
    "clean_hard_assignment_every_seed_min": 0.90,
    "clean_hard_assignment_aggregate_min": 0.95,
    "clean_soft_oracle_query_mass_every_seed_min": 0.30,
    "clean_soft_oracle_query_mass_aggregate_min": 0.35,
    "death_precision_every_seed_min": 1.0,
    "death_recall_every_seed_min": 1.0,
    "death_f1_every_seed_min": 1.0,
    "birth_precision_every_seed_min": 1.0,
    "birth_recall_every_seed_min": 1.0,
    "birth_f1_every_seed_min": 1.0,
    "death_exact_set_every_seed_min": 1.0,
    "birth_exact_set_every_seed_min": 1.0,
    "null_exact_case_every_seed_min": 1.0,
    "null_class_balanced_macro_f1_every_seed_min": 1.0,
    "null_balanced_accuracy_every_seed_min": 1.0,
    "death_positive_support_per_clean_case_min": 1,
    "birth_positive_support_per_clean_case_min": 1,
    "strict_augmented_gap_every_case_min": 0.03,
    "challenge_hard_assignment_every_seed_min": 0.70,
    "challenge_hard_assignment_aggregate_min": 0.80,
    "challenge_soft_oracle_query_mass_every_seed_min": 0.30,
    "challenge_soft_oracle_query_mass_aggregate_min": 0.35,
    "mediator_persistent_macro_f1_every_seed_and_stratum_min": 0.80,
    "mediator_persistent_macro_f1_aggregate_min": 0.85,
    "binding_aggregate_delta_percentage_points_min": 5.0,
    "clean_hungarian_noninferiority_every_seed_margin": 0.10,
    "clean_hungarian_noninferiority_aggregate_margin": 0.05,
    "challenge_fixed_solver_improvement_every_seed_min": 0.20,
    "challenge_main_minus_local_row_top1_accuracy_every_seed_min": 0.20,
    "shared_projector_macro_f1_noninferiority_margin": 0.05
  },
  "fixture_leakage_attack": {
    "name": "per_view_row_argmax_target_state",
    "scope": "challenge_persistent_labels_only",
    "signatures": ["view_1", "view_2", "combined_views"],
    "query_row": "visible_prior_query_marker_row",
    "target_selection": "set_of_all_maximum_cosine_anatomy_compatible_current_endpoints",
    "prediction": "signature_of_sorted_target_state_tuple_over_the_complete_maximum_set",
    "training_or_fitting": "none_deterministic_attack",
    "required_label_balance": "exact_signature_counts_per_label_on_train_inner_development_and_development",
    "source_certificate_splits": ["train", "inner_development", "development"],
    "runtime_gating_split": "development",
    "accuracy_max": 0.3333333333333333,
    "macro_f1_max": 0.3333333333333333,
    "numeric_tolerance": 0.0000001,
    "frozen_deterministic_accuracy_upper_bound_each_signature": 0.3333333333333333,
    "frozen_train_to_development_accuracy": 0.3333333432674408,
    "frozen_train_to_development_macro_f1": 0.16666666666666666,
    "frozen_unseen_development_signature_count": 0,
    "failure_status": "STOP_FIXTURE_LEAKAGE"
  },
  "null_metric_schema": {
    "event_types": ["death", "birth"],
    "required_counts": ["tp", "fp", "fn", "tn", "gold_positive", "predicted_positive"],
    "required_metrics": ["precision", "recall", "f1", "balanced_accuracy", "exact_set_per_case", "micro", "macro"],
    "clean_gold_events_per_case": {"death": 2, "birth": 2},
    "positive_support_required": true,
    "zero_prediction_with_positive_support": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
    "zero_gold_support_action": "ineligible",
    "confusion_arithmetic_recomputed": true,
    "ordinary_accuracy_role": "non_gating_diagnostic"
  },
  "exact64": {
    "global_context": 4,
    "entity": 28,
    "relation_change": 28,
    "neutral_reserved": 4,
    "total": 64,
    "method_order": [
      "oracle",
      "main",
      "local_independent",
      "fixed_hungarian",
      "fixed_sinkhorn",
      "B4b_oracle",
      "B4a_deranged_81001",
      "B4a_deranged_81002",
      "B4a_deranged_81003"
    ],
    "loop_order": ["seed", "stratum", "split", "method"],
    "seed_order": [17, 29, 43],
    "stratum_order": ["clean", "challenge"],
    "split_order": ["development"],
    "expected_call_count": 54,
    "local_adapter": "independent_fixed_budget_local_relation_token_adapter_without_matchplan_validation",
    "ledger_schema_version": "r5_exact64_call_ledger_v1",
    "required_call_hashes": [
      "plan_or_local_weight",
      "candidate_order",
      "allocation",
      "token_value",
      "token_type",
      "attention_mask",
      "position_id",
      "placeholder_position",
      "projected_embedding",
      "readout",
      "adapter",
      "score"
    ]
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
  "run_mode_contract": {
    "registered": {"seeds": [17, 29, 43], "steps": 500, "dry_run": false, "smoke": false},
    "dry_run": {"trains_models": false, "method_gate_pass_forbidden": true},
    "smoke": {"seeds": [17], "actual_steps": 1, "method_gate_pass_forbidden": true},
    "output_root_must_not_exist_at_cli_entry": true,
    "output_parent_must_be_writable": true,
    "formal_test_status": "SEALED",
    "formal_claim_flags": false,
    "success_status_before_reproduction": "PASS_R5_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
    "success_status_after_reproduction": "PASS_R5_SYNTHETIC_ENGINEERING",
    "fixture_leakage_status": "STOP_FIXTURE_LEAKAGE",
    "technical_exception_status": "TECHNICAL_FAILURE_R5_UNHANDLED_EXCEPTION"
  },
  "data_access_contract": {
    "ledger_schema_version": "r5_split_access_ledger_v1",
    "gate_0_resolution_freeze": [],
    "gate_1_structural_input": [
      "clean_structural_audit_fixture_only",
      "challenge_structural_audit_fixture_only"
    ],
    "gate_2_fixture_identifiability": [
      "clean_train_fixture_audit_only",
      "challenge_train_fixture_audit_only",
      "clean_fixture_development_seed_96531",
      "challenge_fixture_development_seed_93531",
      "verify_source_hashed_per_view_row_argmax_target_state_certificate_without_registered_development_access"
    ],
    "gate_3_transport_competence_order": [
      "cache_clean_train_for_training",
      "cache_challenge_train_for_training",
      "freeze_transport_checkpoint",
      "materialize_clean_inner_development",
      "materialize_challenge_inner_development",
      "materialize_clean_development"
    ],
    "gate_4_anti_equivalence_order": [
      "materialize_challenge_development",
      "repeat_per_view_row_argmax_target_state_attack",
      "evaluate_main_anti_equivalence_only_after_attack_passes"
    ],
    "gate_5_mediator_recovery_order": [
      "cache_clean_train_for_mediator_training",
      "cache_challenge_train_for_mediator_training",
      "freeze_main_mediator_checkpoint",
      "cache_clean_development_for_scoring",
      "cache_challenge_development_for_scoring"
    ],
    "gate_6_fair_baseline_order": [
      "cache_clean_train_for_local_training",
      "cache_challenge_train_for_local_training",
      "freeze_local_checkpoint",
      "fit_common_oracle_readout_once_on_train",
      "freeze_common_readout_and_adapter",
      "cache_clean_development_for_common_scoring",
      "cache_challenge_development_for_common_scoring"
    ],
    "gate_7_exact64_bridge": ["no_new_split_cache_only"],
    "gate_8_independent_reproduction": ["no_direct_data_access_child_payload_validation_only"],
    "cache_hits_are_ledgered": true,
    "stopped_payload_contains_completed_prefix_only": true,
    "downstream_split_hashes_after_stop_forbidden": true
  },
  "canonical_reproduction": {
    "schema_version": "r5_canonical_reproduction_v1",
    "exact_excluded_paths": [
      "$.walltime_seconds",
      "$.provenance.utc_start",
      "$.provenance.utc_end",
      "$.provenance.monotonic_elapsed_seconds",
      "$.provenance.process_identity",
      "$.provenance.absolute_run_dir",
      "$.provenance.raw_command"
    ],
    "artifact_paths_under_run_dir": "canonicalize_to_run_root_relative_posix_path",
    "normalized_argv_semantic_fields": {
      "mode": "registered",
      "steps": 500,
      "seeds": [17, 29, 43],
      "device": "cpu",
      "dry_run": false,
      "smoke": false
    },
    "normalized_argv_excludes": ["absolute_run_dir"],
    "required_exact_fields": [
      "protocol_id",
      "normalized_argv_semantic_fields",
      "config",
      "environment_contract",
      "source_hashes",
      "access_ledgers",
      "state_hashes",
      "metrics",
      "gate_trace",
      "status"
    ]
  },
  "eligibility_contract": {
    "validator": "strict_recursive_fail_closed",
    "exact_key_sets": true,
    "unknown_or_missing_keys_fail": true,
    "bool_is_not_integer": true,
    "numeric_strings_fail": true,
    "nonfinite_number_fails_recursively": true,
    "stored_passed_booleans_are_recomputed": true,
    "sha256_uuid_absolute_path_timestamp_and_count_arithmetic_validated": true,
    "nested_schema_versions": {
      "resolver": "r5_resolver_v1",
      "access_ledger": "r5_split_access_ledger_v1",
      "initialization": "r5_initialization_v1",
      "transport": "r5_transport_v1",
      "null_metrics": "r5_null_metrics_v1",
      "local_baseline": "r5_local_baseline_v1",
      "common_readout": "r5_common_readout_v1",
      "fixed_baselines": "r5_fixed_baselines_v1",
      "b4": "r5_b4_v1",
      "exact64": "r5_exact64_call_ledger_v1",
      "gate_trace": "r5_gate_trace_v1",
      "summary": "r5_summary_v1"
    },
    "registered_pending_success": {
      "completed_gates": [0, 1, 2, 3, 4, 5, 6, 7],
      "not_run_gates": ["independent_reproduction"],
      "status": "PASS_R5_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION",
      "formal_data_result_forbidden": true
    },
    "stopped_result": {
      "exactly_one_failed_gate": true,
      "completed_prefix_only": true,
      "later_result_keys_forbidden": true
    }
  },
  "failure_evidence_contract": {
    "main_and_launcher_top_level_transaction": true,
    "non_overwriting_atomic_failure_json": true,
    "launcher_failure_stages": [
      "argument_resolution",
      "output_root_creation",
      "child_popen",
      "child_communicate",
      "stdout_write",
      "stderr_write",
      "child_summary_read",
      "child_summary_parse",
      "child_eligibility",
      "canonical_comparison",
      "certificate_write"
    ],
    "child_b_launch_requires_child_a_zero_pending_and_eligible": true,
    "child_raw_summary_and_failure_hashes_preserved": true,
    "technical_failure_never_reclassified_as_method_failure": true,
    "return_zero_only_status": "PASS_R5_SYNTHETIC_ENGINEERING"
  },
  "registered_environment": {
    "device": "cpu",
    "pythonhashseed": "0",
    "omp_num_threads": "1",
    "mkl_num_threads": "1",
    "torch_num_threads": 1,
    "torch_interop_threads": 1,
    "deterministic_algorithms_enabled": true,
    "deterministic_debug_mode_recorded": true,
    "torch_build_and_cuda_availability_recorded": true,
    "locale_recorded": true,
    "timezone_recorded": true,
    "utc_timestamps_required": true,
    "full_environment_dump_forbidden": true
  },
  "slurm_allocation": {
    "job_id": 4161,
    "job_name": "tpami",
    "node": "gpu01",
    "release_after_run": false
  },
  "formal_data_authorization": "HOLD"
}
```

The five initialization values were generated once before the R5 dry-run as
`0.01 * torch.randn(5, generator=torch.Generator(device="cpu").manual_seed(seed), dtype=torch.float32)`
under PyTorch 2.5.1+cu121, then frozen above as literal values. Implementations
must load the literals in the declared order rather than redraw them. They must
recompute the declared little-endian float32 vector and per-parameter hashes,
prove every literal has absolute value at most 0.02, and record a full model-
state hash. Repeated seed hashes must be identical; hashes for 17/29/43 must be
pairwise distinct. Global RNG consumption may not change these values.

## 3. Registered method contract

### 3.1 Query-independent two-sided partial transport

For identity view `v`, the matcher computes cosine utility `c_v(i,j)` from the
sanitized slices `[2:8]` and `[8:14]`. With two learned logits `w`,

```text
c(i,j) = sum_v softmax(w)_v * c_v(i,j)
u(i,j) = c(i,j) + 0.02*tanh(a)*tanh(c(i,j))
u_death(i) = 0.10*tanh(d_raw)
u_birth(j) = 0.10*tanh(b_raw)
```

The matcher has exactly five learned scalar values: two view logits, `a`,
`d_raw`, and `b_raw`. The scalar calibration is monotone because its derivative
is strictly positive throughout the registered parameter range. It therefore
cannot introduce contextual interactions or reverse an edge ordering at fixed
view weights. All effective null utilities are bounded in `[-0.10, 0.10]`.

The support is validity intersected with equality of the frozen coarse anatomy
index. The augmented assignment contains anatomy-compatible real-real edges,
one private death choice for every prior endpoint, one private birth choice for
every current endpoint, dummy completion edges, and no usable dustbin-to-
dustbin shortcut. The soft solver and hard solver consume the identical
utility tensor and support.

The matcher, support, null utilities, marginals, solver, and allocator may not
read query content or location, state channel `[1:2]`, labels, answer choices,
reports, oracle IDs, gold match count, sample/split identity, padding count,
patient/study IDs, generator seed, or checkpoint-selection metrics. Gold plans
are transport targets only. Changing the query on a fixed pair must preserve
utility, soft-plan, hard-plan, allocation, and token hashes exactly.

### 3.2 Post-transport query gate

One plan is computed for the complete prior/current endpoint sets. Persistent,
death, and birth relation candidates are formed from that plan. Only then may
the query gate weight the relation/change candidates consumed by the mediator.
It may not edit, mask, sharpen, renormalize, or recompute transport. Multiple
queries on the same pair must share the same plan and allocation hashes. Query-
specific outputs are permitted only after the recorded gate.

Training is sequential. Stage 1 trains only the five utility scalars for 500
steps using oracle transport targets, freezes the final state, and records the
state and optimizer hashes. Stage 2 trains the query gate/projector/readout for
500 steps using labels while the matcher and plans are detached and frozen. A
nonzero matcher gradient or a changed matcher hash during Stage 2 fails the
structural gate. Neither stage uses best-checkpoint selection.

This direct transport supervision is an E1 engineering device. It is not a
deployable real-data training recipe and cannot support a clinical or real-
image claim.

## 4. Frozen data-generating processes

### 4.1 Clean stratum

Each case has 14 prior and 14 current endpoints: 12 persistent endpoints in
two six-endpoint anatomy blocks, two true deaths, and two true births. Features
have 18 channels under Section 2. Both identity views encode the same unique
global persistent mapping after independent six-dimensional orthogonal basis
rotations and held-out endpoint permutations. In each anatomy/view, the six
persistent identities are the centered, normalized vertices of a regular
six-simplex: gold cosine is 1 and every off-diagonal cosine is -0.2. The prior
and current null endpoints lie on opposite signs of the orthogonal all-ones
axis, so their cosine is -1 and every persistent-null cosine is zero. Death
endpoints additionally have directional one-hot support in channels 14/15;
birth endpoints have directional one-hot support in channels 16/17. These
support channels remain outside the identity scorer.

Each nuisance group contains `3 query identities x 5 labels = 15` cases. The
five labels are stable, worse, improved, new, and resolved. Counts are 60 train,
30 inner-development, and 90 development cases. The one-sided label ceiling is
0.20 for the five-label audit after removing the query marker; for the
persistent three-label audit with the pre-label marker held fixed it is 1/3.
Both views must independently recover the exact same gold persistent mapping.
The split seeds and visible/hidden hashes are exactly those in the machine
registry; any mismatch is source/fixture drift at Gate 0.

### 4.2 Anti-equivalence challenge

Each challenge case has 12 persistent endpoints, two six-endpoint anatomy
blocks, no birth/death event, and three persistent labels. View 1 encodes the
unique gold global mapping. View 2 is a frozen, anatomy-compatible distractor
permutation constructed before the query/label loop and disjoint from every
gold edge: within each anatomy, three query-role prior endpoints map to the
three guard currents, while three guard-role priors map by a fixed cycle to the
three query currents. The source-hashed feasible witness uses view weights
`[0.95, 0.05]` and recovers gold exactly; equal-view concatenation has exact
gold-mapping accuracy 0.0 and query-label accuracy 1/3. Every
nuisance group contains `3 query identities x 3 labels = 9` cases, giving 36
train, 18 inner-development, and 54 development cases. Each fixed pre-label
group has all three labels, so the one-sided ceiling is 1/3.

Fixture validity additionally includes the deterministic
`per_view_row_argmax_target_state` attack. For view 1, view 2, and their combined
signature separately, it collects the target-state tuple at all maximum-cosine
anatomy-compatible endpoints of the visible prior query row. It has no fitted
parameters. Train, inner-development, and development must have exact per-label
signature counts and deterministic accuracy upper bound 1/3 for all three
signatures. The frozen train-to-development lookup has zero unseen signatures,
accuracy `0.3333333432674408`, and macro-F1 `0.16666666666666666`; float
comparisons use tolerance `1e-7`. A violation is `STOP_FIXTURE_LEAKAGE`, before
any transport competence or method result is interpreted. The registered
runner verifies the frozen source/test certificate at Gate 2 without
materializing registered challenge development; after Gate 3 passes, Gate 4
repeats the attack on the newly authorized development snapshot.

Within every counterfactual group, the allowed per-side multisets, one-sided
permutation-invariant summaries, anatomy and null counts, token counts, and
query-location distribution are fixed. Only the pair-axis correspondence
changes the required label. Current-only, prior-only, separate-pooling, late-
fusion, marker lookup, order, count, padding, and repeated-signature controls
must remain at their analytic ceiling and all trained no-pair-axis controls
must have development macro-F1 at most 0.45.

Train, inner-development, and development tensors are disjoint by generator
seed and full ordered tensor hash. Formal test data do not enter R5.

## 5. Strict augmented assignment certificate

The certificate is evaluated separately for every clean and challenge
development case and every trainable seed at the frozen Stage-1 checkpoint.
It covers the complete augmented feasible assignment, including real-real,
death, birth, anatomy mask, and dummy-completion decisions; a real-real-only
margin is insufficient.

For a case, cast the frozen utility tensor to binary64. Let `S_gold` be the
objective of the complete gold augmented plan. For each semantic edge used by
that plan (real-real, private death, or private birth), forbid that edge and
solve the same augmented Hungarian problem. Dummy-completion edges are excluded
because their permutations represent the same projected partial-transport
plan. The largest objective among these constrained solves is `S_second`.
Every non-gold projected plan omits at least one gold semantic edge, so this
procedure exactly finds the best competing projected plan while quotienting
out irrelevant dummy-completion symmetry. The registered gap is
`S_gold - S_second`. The gold plan must also equal the unconstrained optimum;
the hard solver objective must agree with `S_gold` within `1e-8`; each
constrained solve uses the same lexicographic tie rule; and the gap must be at
least 0.03 for every case. NaN, infinity, a tie, solver disagreement, or a
missing feasible constrained solve fails the gate.

The threshold authority is
`src/visualvit/calibration_r5.py::enumerate_r5_clean_assignment_certificate`
at the exact source/dependency/test hashes in Section 2. It exhausts 130,922
partial bijections for one canonical seven-endpoint anatomy block. The two
clean views have the same cosine matrix, so the enumeration covers the complete
two-view probability simplex. It takes the adverse residual sign throughout
the effective cap `0.02` and the adverse death/birth utilities throughout
`[-0.10, 0.10]`. Its analytic minimum is `0.7847681168808847`. The frozen
float32 cosine-error cap is `5e-7` per edge and its worst-case gap deduction is
`6.63e-6`, producing the registered robust lower bound
`0.7847614868808847`. The canonical certificate JSON SHA-256 is
`51d3374f0b2c9b5376f7f2f355da0fb158797f1ca1a5582481d83a550bdaddde`.
The independent challenge view-1 audit has across-split minimum best-versus-
second global assignment gap `0.36974024772644043`.

The registered design witness is view weights `[0.95, 0.05]`, zero effective
scalar monotone coefficient, and effective death/birth utilities `0.05/0.05`
(raw values `0.5493061443340549/0.5493061443340549`). It demonstrates a
feasible point but is not the source of the robust clean lower bound. The
runtime threshold 0.03 is strictly below both source-hashed design margins and
was fixed before R5 training. Gate 0 recomputes the source and certificate
hashes; Gate 2 verifies the source-hashed design certificate; Gate 3/4 perform
the per-case frozen-checkpoint augmented certificate. Source drift, a changed
fixture hash, or a changed certificate value fails before method evidence is
eligible.

## 6. Null metrics and competence gates

Ordinary null accuracy is diagnostic only because it is dominated by
persistent negatives. On every clean development case, construct the predicted
death set and birth set from the hard augmented plan. Record death and birth
TP/FP/FN/TN, positive support, predicted-positive support, precision, recall,
F1, balanced accuracy, micro/macro aggregates, and exact set equality. Record
separate death-exact and birth-exact rates plus `null_exact_case`, which is one
only when both predicted sets equal both gold sets for that case. With positive
gold support and zero predictions, precision/recall/F1 are zero. Zero gold
support makes the clean null payload ineligible rather than perfect. Confusion
counts, supports, aggregates, and derived metrics are recomputed by eligibility
validation and may not be trusted from stored booleans.

Every clean case must contain exactly two gold deaths and two gold births.
Every seed must achieve death precision/recall/F1/exact-set = 1.0, birth
precision/recall/F1/exact-set = 1.0, joint null-exact-case = 1.0, null class-
balanced macro-F1 = 1.0, and null balanced accuracy = 1.0. Ordinary null
accuracy is non-gating. These gates cannot be rescued by aggregate assignment
accuracy. The remaining numerical thresholds are exactly those in Section 2.
All gradients must be finite on all 500 steps, at least one utility gradient
must be nonzero, the optimizer may own only the registered utility parameters,
and the final matcher hash must differ from its seed-specific initialization
and remain unchanged after freezing.

## 7. Matched trainable baseline and common readout

The strongest trainable assignment baseline has exactly the same five utility
parameters, literal seed-specific initialization, allowed inputs, support,
oracle supervision targets, optimizer, learning rate, weight decay, gradient
clip, 500 steps, splits, and final-step rule as the main matcher. Its only
difference is the absence of global transport competition:

1. each prior row applies a local softmax over anatomy-compatible current
   endpoints plus its death option;
2. two prior rows may select the same current endpoint; no column capacity is
   enforced and duplicate-current rate and overcommitment mass are recorded;
3. a current endpoint's independent birth weight is
   `sigmoid(u_birth/0.05) * product_i(1-p_row_real(i,j))` over compatible prior
   rows, without column normalization, clipping, ranking, or one-to-one repair;
4. the loss is mean oracle row NLL plus mean oracle birth binary cross entropy;
5. the assignment estimand is `row_top1_accuracy`: each prior row's argmax over
   compatible real endpoints plus its private death is compared with that
   row's oracle target. A row is correct only when the oracle target is the
   unique maximizer; non-unique maxima score zero. Duplicate current argmaxes
   across different rows remain duplicate.

The local output is not a feasible partial-transport plan and is never called a
hard `MatchPlan`. It must not call `MatchPlan.validate`, Sinkhorn, Hungarian,
mutual argmax, greedy one-to-one, column softmax/normalization, cross-row top-k,
or any repair that selects among prior rows competing for one current. Its
independent fixed-budget local relation-token adapter consumes row probabilities,
private-death probabilities, and birth weights directly and fills the same 28
relation/change positions. Parameter counts, optimizer updates, training order,
operation-count proxy, row-normalization error, duplicate rate, overcommitment,
state hashes, and adapter call evidence are mandatory. The challenge must
exhibit at least one duplicate-current collision or the baseline is ineligible.

Gate 6 fits one **common oracle-frozen readout** per trainable seed, exactly once
and on registered train data only. The joint batch order is clean then
challenge; training uses the Section-2 CE/AdamW configuration for 500 steps.
The projector seed is the trainable seed, the frozen adapter seed is 91001, and
the query dimensions are 6 to 8. After fitting, projector and adapter are
frozen and their state hashes are attached unchanged to, in exact order:
`oracle`, `main`, `local_independent`, `fixed_hungarian`, `fixed_sinkhorn`,
`B4b_oracle`, and B4a derangements 81001/81002/81003. Each result records the
same readout hash for its seed, `fit_count=1`, and
`post_freeze_update_count=0`. The local method reaches this readout through its
independent fixed-budget adapter, never through `MatchPlan.validate`.

A baseline may not reuse a projector or mediator trained on main predictions.
The separately trained R5 main mediator remains under the disjoint result key
declared in Section 2 and is used only at Gate 5. Under Gate 6, main challenge
hard assignment accuracy must exceed local `row_top1_accuracy` by at least
0.20 for every seed. Under the common readout, main macro-F1 may be no worse
than local by more than 0.05 on any seed/stratum. Main clean hard assignment
must be within 0.10 of visible-cosine Hungarian for every seed and 0.05 in
aggregate; challenge main must exceed the best fixed visible-cosine Hungarian
or balanced-Sinkhorn hard assignment by at least 0.20 for every seed. The
fixed methods share the equal-view utility, support, null policy, splits,
budget, and common readout.

## 8. Structural, causal, and exact-64 audits

Before competence metrics are eligible, direct tests must pass for: soft mass
accounting and feasibility; finite differentiation; hard global optimality on
enumerated micro-cases; query independence; hidden-ID invariance; endpoint
permutation equivariance; state-channel zeroing invariance; forbidden-channel
zeroing invariance; two-sided reject behavior; deterministic ties; and
soft/hard use of the same utility and support. Competence probes and controls
may not mutate any actual training or development tensor.

The B4 binding pair uses identical visible features, candidate universe,
birth/death sets, query, token layout, projector, frozen adapter, readout,
optimizer, steps, and seed. B4b receives the correct assignment; B4a receives a
source-hashed anatomy-compatible cyclic derangement. Only the assignment and
relation values causally downstream of it may differ. The oracle competence
denominator must be positive and the aggregate B4b-minus-B4a persistent
macro-F1 must be at least 5.0 percentage points.

Every frozen-model bridge method physically supplies exactly:

```text
4 global/context + 28 entity + 28 relation/change + 4 neutral/reserved = 64
```

All positions exist for every method. Invalid and reserved positions receive
one shared neutral representation; positions may not be deleted or shortened.
Allocation, type, source support, physical mask, prompt placeholders, position
IDs, attention, label strings, normalized-likelihood scorer, batch order,
adapter, and frozen model are identical. Exactly 64 placeholders are replaced,
no raw pixel bypass reaches the relation path, and backbone/frozen-parameter,
allocation, token, mask, position, and observed-call hashes are recorded.

Gate 7 creates no split. It reuses immutable Gate-6 development snapshots and
executes the exact nested order `seed 17/29/43`, `clean/challenge`,
`development`, then the nine-method order frozen in Section 2, for exactly 54
ledger calls. Every call records its ordinal and all hashes named by the
machine registry. A swapped, skipped, duplicated, performance-selected, or
extra call fails. The common-readout hash is identical across all nine methods
within a seed. Hidden-ID, restored endpoint-permutation, and B4 isomorphism
audits are repeated through the adapter. The local call uses its independent
fixed-budget local adapter. Candidate/token ordering and every Gate-6 required
main-versus-control ordering or margin must survive the exact-64 bridge; a tie,
missing method, new split access, or parameter update fails Gate 7.

## 9. Stop-first-fail gate order

The runner stops at the first failed gate and does not compute later-gate
evidence:

0. protocol/config/source hashes, unique output root, literal seed
   initialization, and runtime resolution;
1. structural/input/leakage/two-sided-null/exact-64 property audits;
2. clean and challenge fixture identifiability, source-hashed per-view leakage
   attack, and all bypass ceilings; leakage uses `STOP_FIXTURE_LEAKAGE`;
3. separated transport competence, strict augmented gap, and exact null gates;
4. anti-equivalence hard/soft recovery under one query-independent plan;
5. frozen-matcher mediator recovery and B4 assignment effect;
6. fixed-solver and matched-trainable fair-baseline comparisons with the common
   oracle-frozen projector;
7. exact-64 frozen-adapter bridge and isomorphism hashes;
8. two-process independent reproduction;
9. formal-data authorization, which remains `HOLD` and is not executed.

The machine-readable access matrix is normative. Gate 0 has no split provider
and must finish config/source/environment resolution before any registered or
audit fixture is generated. Gate 1 may use only independent structural audit
fixtures and computes no label metric. Gate 2 may inspect registered train for
fixture properties and the independent fixture-development seeds 96531/93531;
it verifies the source-hashed registered-development leakage certificate but
does not materialize registered inner-development or development. Gate 3 uses
the cached train batches, finishes and freezes transport, then accesses inner-
development, and only then clean development. Gate 4 first materializes
challenge development, repeats the leakage attack, and stops before main
challenge scoring if it fails. Gate 5 trains and freezes the separate main
mediator before development scoring. Gate 6 trains and freezes the local
baseline, fits/freezes the common oracle readout once on train, and only then
performs common-readout development scoring. Gate 7 uses caches only; Gate 8
reads child payloads only.

The sole accessor appends gate, stratum, split or audit-fixture name, purpose,
content hash, and cache-hit status to an append-only ledger before returning a
batch. An out-of-order request raises `PrematureDataAccessError` and creates a
technical failure. Every stop emits exactly the completed gate/access prefix;
later gate keys and later split hashes are absent. Thus “ordered split hashes”
below always means hashes of **accessed and authorized** splits, never eager
materialization of the complete split bank.

A one-step smoke uses seed 17 only and may report diagnostics but cannot pass
gates 3-8. A registered primary uses exactly seeds 17/29/43 and 500 steps per
stage. Before reproduction it may report only
`PASS_R5_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION`. After two eligible
replicas match it may report only `PASS_R5_SYNTHETIC_ENGINEERING`. Failures use
`STOP_R5_<FIRST_GATE_NAME>` and a nonzero exit code. An unhandled exception uses
`TECHNICAL_FAILURE_R5_UNHANDLED_EXCEPTION` and is never a scientific stop.

## 10. Eligibility, provenance, and reproduction

Every dry-run, smoke, primary, and replica uses a new non-existing output
directory. The source manifest contains the R5 protocol, runner, reproduction
launcher, all imported method/generator/adapter modules, focused tests,
dependency specification, the R5 gate specification, and inherited R2/R3
protocols under a closed allowlist. Gate 0 recomputes the exact enumerator,
dependency, test, gate-spec, fixture, and certificate hashes frozen in Section
2; a missing, extra, or changed authority file fails. Each artifact records
the composite source hash, config hash, exact command, environment, hardware,
process PID and UUID, authorized accessed-split tensor hashes and ledger,
literal initialization and state hashes, optimizer hashes, parameter names/
counts, gradient audits, utility/plan/allocation/token hashes, gate trace,
first stop reason, and formal-test seal.

A registered primary is eligible for reproduction only when it is neither dry-
run nor smoke; uses exactly all three seeds and 500 steps; has finite gradients
for every registered step; passes gates 0-7 in order; retains an unchanged
frozen matcher during mediator training; uses `PYTHONHASHSEED=0`,
`OMP_NUM_THREADS=1`, and `MKL_NUM_THREADS=1`; records formal test `SEALED` and
formal data `HOLD`; and has no source/config drift.

Eligibility is a recursive exact-schema validation, not a collection of trusted
`passed` booleans. Every registered object uses the nested schema version in
Section 2; missing or unknown keys, a boolean in an integer field, numeric
strings, non-finite values, invalid hashes/UUIDs/timestamps, wrong seed/method/
split sets, inconsistent confusion counts or averages, forged derived values,
or a later-stage key after stop fails eligibility. The validator recomputes
gate verdicts, access prefixes, arithmetic, hashes, state transitions, and
status. Two canonically equal malformed replicas remain ineligible.

The reproduction launcher starts replica A and then replica B as fresh,
sequential processes. Replica B is not started if A is ineligible or exits
nonzero. Both replicas must have distinct valid UUIDs and launcher-matching
PIDs. Canonical payload equality is exact after excluding only wall-clock time
and the other exact volatile provenance paths frozen in Section 2. Raw command,
absolute run directory, UTC start/end timestamps, monotonic elapsed time, and
process identity remain preserved in each raw child artifact but are excluded
from the canonical comparison. Every artifact path under the run root is first
normalized to a run-root-relative POSIX path. The canonical payload retains the
normalized semantic argv—registered mode, steps 500, seeds 17/29/43, CPU,
`dry_run=false`, and `smoke=false`—while excluding only the absolute run-dir
argument. Config, environment contract, source/fixture hashes, access ledgers,
state hashes, metrics, gates, and status are exact and cannot be excluded.
Both canonical JSON hashes must be identical. An unlisted volatile path, schema
drift, or mismatch fails Gate 8 and may not be rounded away.

The main runner and reproduction launcher each use a top-level fail-closed
transaction. Every exception stage listed in Section 2 best-effort publishes a
non-overwriting atomic `failure.json` containing the stage, error/traceback,
launcher provenance, whitelisted environment, child command/PID/return code
where known, and hashes of raw logs or child artifacts. Replica B is launched
only after A exits zero, has the exact pending status, and independently passes
strict eligibility. A child technical failure is preserved by raw hash and is
never rewritten as a method stop. Only the final exact reproduction success
status returns zero.

No architecture, input, utility, cap, initialization, solver, loss, split,
seed, step count, optimizer, checkpoint rule, threshold, baseline, token
interface, gate order, or canonical payload field may change after the first R5
dry-run begins. Any such change supersedes R5 and requires a new protocol ID,
new manifest, and new output roots. Negative and technical artifacts remain
visible.

## 11. Formal-data HOLD and allocation 4161

R5 authorizes only E0 unit/analytic checks and E1 synthetic engineering. It
does not authorize model or dataset downloads, real-image training, clinical
claims, GPU scale-up, or formal-test reveal. E2 proxy, E3 frozen-VLM bridge, E4
real train/development pilot, and E5 sealed evaluation each require a separate
data and execution authority.

CheXTemporal metadata do not establish one-to-one per-box progression or a
persistent-entity oracle. CheXpert, MIMIC-CXR, MS-CXR-T, Chest ImaGenome,
ReXGradient, and any replacement dataset remain `HOLD` until license/DUA/CITI
access, patient/study/image lineage, annotation granularity, cross-source de-
duplication, patient-level splits, power/endpoints, and a sealed formal test are
documented and source-hashed.

The E0/E1 registered CPU process may run inside retained Slurm allocation
`4161` (`tpami`, `gpu01`) after local gates pass. Allocation 4161 must never be
cancelled, released, or allowed to terminate as a cleanup action. Completion,
failure, reproduction, or this protocol's formal-data `HOLD` does not authorize
`scancel 4161`. The reserved GPU remains untouched by this CPU-only synthetic
calibration unless a later protocol explicitly authorizes a GPU bridge.
