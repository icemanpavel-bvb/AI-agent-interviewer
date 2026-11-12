# Оценка качества

Синтетические диалоги прогоняются через Interview Engine и Report Builder, затем считаются метрики из ARCHITECTURE.md §11.

```
python eval/run_eval.py --dataset eval/datasets/synthetic_dialogs.jsonl --vacancy eval/datasets/vacancy_backend.json
```
