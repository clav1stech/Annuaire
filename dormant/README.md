# Dossier dormant — fonctionnalités mises de côté

Ce dossier regroupe des fonctionnalités **dépréciées / non maintenues**, conservées
pour référence mais volontairement exclues du flux applicatif principal. Elles ne
sont ni lancées par `run_app.sh` / `run_app.bat`, ni documentées dans le README
principal.

## `name_search_app.py` — Recherche de candidats SIRENE par nom

App Streamlit secondaire qui, à partir d'une feuille *anomalies* produite par
l'app principale, tentait de retrouver jusqu'à 3 candidats SIRENE par recherche
floue sur le nom d'entreprise + code postal.

**Statut : déprécié.** La recherche par nom n'est pas assez fiable (trop de
faux positifs / candidats non pertinents) pour être exploitable en production.
La fonctionnalité est mise de côté en attendant une éventuelle refonte de
l'heuristique de matching.

### Dépendances restées dans `src/`

Les fonctions support ne sont utilisées que par cette app dormante :
- `src/sirene_queries.py` → `SireneQueryService.search_candidates_by_text`
- `src/export_utils.py` → `to_name_search_excel_bytes`

Elles sont laissées en place (inertes tant que l'app n'est pas lancée) pour ne
pas fragiliser les modules partagés. À supprimer si la fonctionnalité est
définitivement abandonnée.

### Relancer manuellement (si besoin de tester)

Les imports `from src...` supposent la racine du projet sur le `PYTHONPATH`.
Depuis la racine du projet, après avoir créé l'environnement virtuel :

```bash
PYTHONPATH=. .venv_annuaire_sirene/bin/streamlit run dormant/name_search_app.py --server.port 8502
```
