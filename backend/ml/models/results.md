
 docker compose --profile train run --rm ml
WARN[0000] Found orphan containers (predicare-tpa-prepare-1) for this project. If you removed or renamed this service in your compose file, you can run this command with the --remove-orphans flag to clean it up.
[+] run 1/1
 ✔ Container predicare-tpa-mlflow-1 Running                                                                                          0.0s
Container predicare-tpa-mlflow-1 Waiting
Container predicare-tpa-mlflow-1 Healthy
Container predicare-tpa-ml-run-a0566b3c1d3d Creating
Container predicare-tpa-ml-run-a0566b3c1d3d Created
84593 factures, 85 variables, fraude 8.69% | fenêtres {'train': ['2024-10-01', '2026-01-21'], 'valid': ['2026-01-22', '2026-05-03'], 'test': ['2026-05-04', '2026-10-01']}

== baseline_logreg
    baseline_logreg        {} -> PR-AUC valid 0.9752 (7s)

== hgb_poids
    hgb_poids              {'min_samples_leaf': 10, 'max_leaf_nodes': 31, 'learning_rate': 0.03, 'l2_regularization': 1.0} -> PR-AUC valid 0.9984 (14s)
    hgb_poids              {'min_samples_leaf': 10, 'max_leaf_nodes': 15, 'learning_rate': 0.03, 'l2_regularization': 0.0} -> PR-AUC valid 0.9981 (14s)
    hgb_poids              {'min_samples_leaf': 30, 'max_leaf_nodes': 31, 'learning_rate': 0.1, 'l2_regularization': 0.0} -> PR-AUC valid 0.9985 (12s)
    hgb_poids              {'min_samples_leaf': 30, 'max_leaf_nodes': 31, 'learning_rate': 0.03, 'l2_regularization': 1.0} -> PR-AUC valid 0.9983 (16s)
    hgb_poids              {'min_samples_leaf': 10, 'max_leaf_nodes': 15, 'learning_rate': 0.1, 'l2_regularization': 0.0} -> PR-AUC valid 0.9985 (11s)
    hgb_poids              {'min_samples_leaf': 30, 'max_leaf_nodes': 15, 'learning_rate': 0.03, 'l2_regularization': 1.0} -> PR-AUC valid 0.9980 (15s)
    hgb_poids              {'min_samples_leaf': 30, 'max_leaf_nodes': 15, 'learning_rate': 0.06, 'l2_regularization': 0.0} -> PR-AUC valid 0.9987 (13s)
    hgb_poids              {'min_samples_leaf': 30, 'max_leaf_nodes': 63, 'learning_rate': 0.06, 'l2_regularization': 5.0} -> PR-AUC valid 0.9978 (12s)
    hgb_poids              {'min_samples_leaf': 30, 'max_leaf_nodes': 31, 'learning_rate': 0.03, 'l2_regularization': 0.0} -> PR-AUC valid 0.9984 (14s)
    hgb_poids              {'min_samples_leaf': 10, 'max_leaf_nodes': 31, 'learning_rate': 0.06, 'l2_regularization': 0.0} -> PR-AUC valid 0.9985 (12s)
    hgb_poids              {'min_samples_leaf': 30, 'max_leaf_nodes': 31, 'learning_rate': 0.1, 'l2_regularization': 1.0} -> PR-AUC valid 0.9984 (12s)
    hgb_poids              {'min_samples_leaf': 10, 'max_leaf_nodes': 63, 'learning_rate': 0.03, 'l2_regularization': 1.0} -> PR-AUC valid 0.9982 (17s)

== hgb_smote
    hgb_smote              {'min_samples_leaf': 10, 'max_leaf_nodes': 31, 'learning_rate': 0.03, 'l2_regularization': 1.0} -> PR-AUC valid 0.9979 (36s)
    hgb_smote              {'min_samples_leaf': 10, 'max_leaf_nodes': 15, 'learning_rate': 0.03, 'l2_regularization': 0.0} -> PR-AUC valid 0.9979 (33s)
    hgb_smote              {'min_samples_leaf': 30, 'max_leaf_nodes': 31, 'learning_rate': 0.1, 'l2_regularization': 0.0} -> PR-AUC valid 0.9985 (32s)
    hgb_smote              {'min_samples_leaf': 30, 'max_leaf_nodes': 31, 'learning_rate': 0.03, 'l2_regularization': 1.0} -> PR-AUC valid 0.9980 (36s)
    hgb_smote              {'min_samples_leaf': 10, 'max_leaf_nodes': 15, 'learning_rate': 0.1, 'l2_regularization': 0.0} -> PR-AUC valid 0.9984 (36s)
    hgb_smote              {'min_samples_leaf': 30, 'max_leaf_nodes': 15, 'learning_rate': 0.03, 'l2_regularization': 1.0} -> PR-AUC valid 0.9976 (37s)
    hgb_smote              {'min_samples_leaf': 30, 'max_leaf_nodes': 15, 'learning_rate': 0.06, 'l2_regularization': 0.0} -> PR-AUC valid 0.9984 (37s)
    hgb_smote              {'min_samples_leaf': 30, 'max_leaf_nodes': 63, 'learning_rate': 0.06, 'l2_regularization': 5.0} -> PR-AUC valid 0.9974 (46s)
    hgb_smote              {'min_samples_leaf': 30, 'max_leaf_nodes': 31, 'learning_rate': 0.03, 'l2_regularization': 0.0} -> PR-AUC valid 0.9981 (40s)
    hgb_smote              {'min_samples_leaf': 10, 'max_leaf_nodes': 31, 'learning_rate': 0.06, 'l2_regularization': 0.0} -> PR-AUC valid 0.9984 (37s)
    hgb_smote              {'min_samples_leaf': 30, 'max_leaf_nodes': 31, 'learning_rate': 0.1, 'l2_regularization': 1.0} -> PR-AUC valid 0.9982 (38s)
    hgb_smote              {'min_samples_leaf': 10, 'max_leaf_nodes': 63, 'learning_rate': 0.03, 'l2_regularization': 1.0} -> PR-AUC valid 0.9980 (50s)

== lightgbm_poids
    lightgbm_poids         {'subsample': 0.7, 'reg_lambda': 0.0, 'num_leaves': 31, 'min_child_samples': 60, 'learning_rate': 0.1, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9986 (5s)
    lightgbm_poids         {'subsample': 0.85, 'reg_lambda': 1.0, 'num_leaves': 31, 'min_child_samples': 60, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9985 (5s)
    lightgbm_poids         {'subsample': 1.0, 'reg_lambda': 1.0, 'num_leaves': 15, 'min_child_samples': 60, 'learning_rate': 0.03, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9984 (4s)
    lightgbm_poids         {'subsample': 0.85, 'reg_lambda': 1.0, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9984 (3s)
    lightgbm_poids         {'subsample': 1.0, 'reg_lambda': 0.0, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.03, 'colsample_bytree': 1.0} -> PR-AUC valid 0.9984 (3s)
    lightgbm_poids         {'subsample': 1.0, 'reg_lambda': 1.0, 'num_leaves': 63, 'min_child_samples': 10, 'learning_rate': 0.03, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9985 (6s)
    lightgbm_poids         {'subsample': 0.7, 'reg_lambda': 0.0, 'num_leaves': 63, 'min_child_samples': 60, 'learning_rate': 0.03, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9983 (5s)
    lightgbm_poids         {'subsample': 0.7, 'reg_lambda': 0.0, 'num_leaves': 15, 'min_child_samples': 10, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9985 (3s)
    lightgbm_poids         {'subsample': 0.85, 'reg_lambda': 5.0, 'num_leaves': 63, 'min_child_samples': 30, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9982 (5s)
    lightgbm_poids         {'subsample': 0.7, 'reg_lambda': 0.0, 'num_leaves': 63, 'min_child_samples': 10, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9986 (6s)
    lightgbm_poids         {'subsample': 1.0, 'reg_lambda': 0.0, 'num_leaves': 63, 'min_child_samples': 10, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9988 (6s)
    lightgbm_poids         {'subsample': 0.85, 'reg_lambda': 5.0, 'num_leaves': 15, 'min_child_samples': 60, 'learning_rate': 0.1, 'colsample_bytree': 1.0} -> PR-AUC valid 0.9984 (3s)

== lightgbm_smote
    lightgbm_smote         {'subsample': 0.7, 'reg_lambda': 0.0, 'num_leaves': 31, 'min_child_samples': 60, 'learning_rate': 0.1, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9754 (6s)
    lightgbm_smote         {'subsample': 0.85, 'reg_lambda': 1.0, 'num_leaves': 31, 'min_child_samples': 60, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9611 (6s)
    lightgbm_smote         {'subsample': 1.0, 'reg_lambda': 1.0, 'num_leaves': 15, 'min_child_samples': 60, 'learning_rate': 0.03, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9746 (5s)
    lightgbm_smote         {'subsample': 0.85, 'reg_lambda': 1.0, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9741 (5s)
    lightgbm_smote         {'subsample': 1.0, 'reg_lambda': 0.0, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.03, 'colsample_bytree': 1.0} -> PR-AUC valid 0.9689 (5s)
    lightgbm_smote         {'subsample': 1.0, 'reg_lambda': 1.0, 'num_leaves': 63, 'min_child_samples': 10, 'learning_rate': 0.03, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9892 (9s)
    lightgbm_smote         {'subsample': 0.7, 'reg_lambda': 0.0, 'num_leaves': 63, 'min_child_samples': 60, 'learning_rate': 0.03, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9676 (7s)
    lightgbm_smote         {'subsample': 0.7, 'reg_lambda': 0.0, 'num_leaves': 15, 'min_child_samples': 10, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9399 (4s)
    lightgbm_smote         {'subsample': 0.85, 'reg_lambda': 5.0, 'num_leaves': 63, 'min_child_samples': 30, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9725 (8s)
    lightgbm_smote         {'subsample': 0.7, 'reg_lambda': 0.0, 'num_leaves': 63, 'min_child_samples': 10, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9878 (7s)
    lightgbm_smote         {'subsample': 1.0, 'reg_lambda': 0.0, 'num_leaves': 63, 'min_child_samples': 10, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9811 (7s)
    lightgbm_smote         {'subsample': 0.85, 'reg_lambda': 5.0, 'num_leaves': 15, 'min_child_samples': 60, 'learning_rate': 0.1, 'colsample_bytree': 1.0} -> PR-AUC valid 0.9796 (4s)

== xgboost_poids
    xgboost_poids          {'subsample': 0.7, 'reg_lambda': 0.0, 'min_child_weight': 3, 'max_depth': 8, 'learning_rate': 0.1, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9978 (9s)
    xgboost_poids          {'subsample': 0.85, 'reg_lambda': 1.0, 'min_child_weight': 3, 'max_depth': 8, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9983 (12s)
    xgboost_poids          {'subsample': 1.0, 'reg_lambda': 1.0, 'min_child_weight': 1, 'max_depth': 8, 'learning_rate': 0.03, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9980 (14s)
    xgboost_poids          {'subsample': 0.85, 'reg_lambda': 1.0, 'min_child_weight': 1, 'max_depth': 6, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9981 (5s)
    xgboost_poids          {'subsample': 1.0, 'reg_lambda': 0.0, 'min_child_weight': 1, 'max_depth': 6, 'learning_rate': 0.03, 'colsample_bytree': 1.0} -> PR-AUC valid 0.9972 (10s)
    xgboost_poids          {'subsample': 1.0, 'reg_lambda': 1.0, 'min_child_weight': 8, 'max_depth': 4, 'learning_rate': 0.03, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9925 (7s)
    xgboost_poids          {'subsample': 0.7, 'reg_lambda': 0.0, 'min_child_weight': 8, 'max_depth': 8, 'learning_rate': 0.03, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9978 (8s)
    xgboost_poids          {'subsample': 0.7, 'reg_lambda': 0.0, 'min_child_weight': 1, 'max_depth': 4, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9974 (3s)
    xgboost_poids          {'subsample': 0.85, 'reg_lambda': 5.0, 'min_child_weight': 8, 'max_depth': 6, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.9980 (5s)
    xgboost_poids          {'subsample': 0.7, 'reg_lambda': 0.0, 'min_child_weight': 8, 'max_depth': 4, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9975 (3s)
    xgboost_poids          {'subsample': 1.0, 'reg_lambda': 0.0, 'min_child_weight': 8, 'max_depth': 4, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.9974 (3s)
    xgboost_poids          {'subsample': 0.85, 'reg_lambda': 5.0, 'min_child_weight': 1, 'max_depth': 8, 'learning_rate': 0.1, 'colsample_bytree': 1.0} -> PR-AUC valid 0.9979 (7s)

== xgboost_smote
    xgboost_smote          {'subsample': 0.7, 'reg_lambda': 0.0, 'min_child_weight': 3, 'max_depth': 8, 'learning_rate': 0.1, 'colsample_bytree': 0.8} -> PR-AUC valid 0.5040 (10s)
    xgboost_smote          {'subsample': 0.85, 'reg_lambda': 1.0, 'min_child_weight': 3, 'max_depth': 8, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.5241 (9s)
    xgboost_smote          {'subsample': 1.0, 'reg_lambda': 1.0, 'min_child_weight': 1, 'max_depth': 8, 'learning_rate': 0.03, 'colsample_bytree': 0.8} -> PR-AUC valid 0.5154 (9s)
    xgboost_smote          {'subsample': 0.85, 'reg_lambda': 1.0, 'min_child_weight': 1, 'max_depth': 6, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.4641 (8s)
    xgboost_smote          {'subsample': 1.0, 'reg_lambda': 0.0, 'min_child_weight': 1, 'max_depth': 6, 'learning_rate': 0.03, 'colsample_bytree': 1.0} -> PR-AUC valid 0.4826 (8s)
    xgboost_smote          {'subsample': 1.0, 'reg_lambda': 1.0, 'min_child_weight': 8, 'max_depth': 4, 'learning_rate': 0.03, 'colsample_bytree': 0.8} -> PR-AUC valid 0.4036 (5s)
    xgboost_smote          {'subsample': 0.7, 'reg_lambda': 0.0, 'min_child_weight': 8, 'max_depth': 8, 'learning_rate': 0.03, 'colsample_bytree': 0.6} -> PR-AUC valid 0.4230 (26s)
    xgboost_smote          {'subsample': 0.7, 'reg_lambda': 0.0, 'min_child_weight': 1, 'max_depth': 4, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.1244 (8s)
    xgboost_smote          {'subsample': 0.85, 'reg_lambda': 5.0, 'min_child_weight': 8, 'max_depth': 6, 'learning_rate': 0.05, 'colsample_bytree': 0.6} -> PR-AUC valid 0.4608 (11s)
    xgboost_smote          {'subsample': 0.7, 'reg_lambda': 0.0, 'min_child_weight': 8, 'max_depth': 4, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.2427 (6s)
    xgboost_smote          {'subsample': 1.0, 'reg_lambda': 0.0, 'min_child_weight': 8, 'max_depth': 4, 'learning_rate': 0.05, 'colsample_bytree': 0.8} -> PR-AUC valid 0.1439 (6s)
    xgboost_smote          {'subsample': 0.85, 'reg_lambda': 5.0, 'min_child_weight': 1, 'max_depth': 8, 'learning_rate': 0.1, 'colsample_bytree': 1.0} -> PR-AUC valid 0.6799 (13s)

       candidat  pr_auc_valid  pr_auc_test  recall_test  precision_test  recall_test_seuil_0.8  precision_test_seuil_0.8
baseline_logreg        0.9752       0.9772       0.9524          0.8614                 0.9262                    0.9274
      hgb_poids        0.9987       0.9986       0.9351          0.9993                 0.9848                    0.9875
      hgb_smote        0.9985       0.9988       0.9358          0.9978                 0.9662                    0.9943
 lightgbm_poids        0.9988       0.9988       0.9469          0.9993                 0.9848                    0.9937
 lightgbm_smote        0.9892       0.9800       0.9282          0.9897                 0.9800                    0.4521
  xgboost_poids        0.9983       0.9981       0.9282          0.9948                 0.9620                    0.9894
  xgboost_smote        0.6799       0.6781       0.9331          0.1783                 0.9551                    0.1667
2026/10/18 11:57:09 INFO mlflow.tracking.fluent: Experiment with name 'predicare-fraude' does not exist. Creating a new experiment.
2026/10/18 11:57:10 WARNING mlflow.utils.git_utils: Failed to import Git (the Git executable is probably not on your PATH), so Git SHA is not available. Error: Failed to initialize: Bad git executable.
The git executable must be specified in one of the following ways:
    - be included in your $PATH
    - be set via $GIT_PYTHON_GIT_EXECUTABLE
    - explicitly set via git.refresh(<full-path-to-git-executable></full>)

All git commands will error until this is rectified.

This initial message can be silenced or aggravated in the future by setting the
$GIT_PYTHON_REFRESH environment variable. Use one of the following values:
    - quiet|q|silence|s|silent|none|n|0: for no message or exception
    - warn|w|warning|log|l|1: for a warning message (logging level CRITICAL, displayed by default)
    - error|e|exception|raise|r|2: for a raised exception

Example:
    export GIT_PYTHON_REFRESH=quiet

2026/10/18 11:57:10 WARNING mlflow.utils.git_utils: Failed to import Git (the Git executable is probably not on your PATH), so Git branch is not available. Error: Failed to initialize: Bad git executable.
The git executable must be specified in one of the following ways:
    - be included in your $PATH
    - be set via $GIT_PYTHON_GIT_EXECUTABLE
    - explicitly set via git.refresh(<full-path-to-git-executable></full>)

All git commands will error until this is rectified.

This initial message can be silenced or aggravated in the future by setting the
$GIT_PYTHON_REFRESH environment variable. Use one of the following values:
    - quiet|q|silence|s|silent|none|n|0: for no message or exception
    - warn|w|warning|log|l|1: for a warning message (logging level CRITICAL, displayed by default)
    - error|e|exception|raise|r|2: for a raised exception

Example:
    export GIT_PYTHON_REFRESH=quiet

2026/10/18 11:57:10 WARNING mlflow.utils.git_utils: Failed to import Git (the Git executable is probably not on your PATH), so Git repository URL is not available. Error: Failed to initialize: Bad git executable.
The git executable must be specified in one of the following ways:
    - be included in your $PATH
    - be set via $GIT_PYTHON_GIT_EXECUTABLE
    - explicitly set via git.refresh(<full-path-to-git-executable></full>)

All git commands will error until this is rectified.

This initial message can be silenced or aggravated in the future by setting the
$GIT_PYTHON_REFRESH environment variable. Use one of the following values:
    - quiet|q|silence|s|silent|none|n|0: for no message or exception
    - warn|w|warning|log|l|1: for a warning message (logging level CRITICAL, displayed by default)
    - error|e|exception|raise|r|2: for a raised exception

Example:
    export GIT_PYTHON_REFRESH=quiet

🏃 View run lightgbm-20261018-1157-078e86 at: http://mlflow:5000/#/experiments/1/runs/9421e2f8840944babee7a9f2e133eb9a
🧪 View experiment at: http://mlflow:5000/#/experiments/1

Modèle retenu : lightgbm-20261018-1157-078e86
  test : {'pr_auc': 0.9988, 'roc_auc': 0.9997, 'seuil': 0.9999, 'recall': 0.9469, 'precision': 0.9993, 'alertes': 1373, 'tp': 1372, 'fp': 1, 'fn': 77, 'au_seuil_cdc': {'seuil': 0.8, 'recall': 0.9848, 'precision': 0.9937, 'alertes': 1436, 'tp': 1427, 'fp': 9, 'fn': 22}}
  recall par type : {'ACTE_FICTIF': 0.837, 'DOUBLON': 0.943, 'FRACTIONNEMENT': 0.828, 'HORS_COUVERTURE': 0.913, 'INCOHERENCE_PROFIL': 1.0, 'LIGNES_NON_PRESCRITES': 1.0, 'ORDONNANCE_EXPIREE': 1.0, 'PRESTATAIRE_RADIE': 0.771, 'QUANTITE_EXCESSIVE': 0.99, 'SOINS_JOUR_FERME': 1.0, 'SUBSTITUTION_PRODUIT': 1.0, 'SURCONSOMMATION': 0.979, 'SURFACTURATION': 0.985, 'UPCODING': 0.909}
PS C:\Users\Public.DESKTOP-O75ICV3\Documents\Formation_ia\PrediCare-TPA>
