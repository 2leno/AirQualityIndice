# ARCHITECTURE.md

Documentation de l'architecture technique du projet **AQI - Air Quality Index ETL Pipeline** (DONNEES2).

## Schéma global

```
Open-Meteo Air Quality API (5 villes de Madagascar)
        │  collecte horaire (temps réel) + backfill (historique jusqu'à 12 mois)
        ▼
ORCHESTRATEUR : Apache Airflow 3.3 (DAG air_quality_pipeline)
        │  extract → save_raw → transform → load → alert
        ▼
STOCKAGE
  data/raw/            fichiers bruts, jamais modifiés (1 fichier par ville et par appel)
  data/raw/backfill/   archives horaires par ville et par mois (historique)
  data/clean/          air_quality.csv unique, reconstruit à chaque run depuis raw/
        ▼
DATA WAREHOUSE : PostgreSQL 16 — schéma en flocon (6 tables)
  dim_region → dim_city, dim_pollutant_category → dim_pollutant, dim_date, fact_air_quality
```

## Stack choisie et justifications

| Composant | Choix | Justification |
|---|---|---|
| **Source de données** | API Open-Meteo Air Quality | Gratuite, sans clé API requise, couvre les 5 villes malgaches choisies et fournit à la fois les mesures en temps réel (`current`) et l'historique (`hourly` sur plage de dates), ce qui simplifie l'extraction et le backfill avec un seul client. |
| **Langage** | Python 3.11+ | Écosystème mature pour l'ETL (Pandas, SQLAlchemy) et compatibilité native avec Airflow ; c'est le langage vu en cours pour l'ETL. |
| **Client API** | `openmeteo-requests` | Client officiel du fournisseur, gère nativement le cache et le retry, évite de réécrire un wrapper HTTP maison. |
| **Transformation** | Pandas | Manipulation tabulaire simple et lisible pour construire les dimensions et la table de faits (melt, merge, dédoublonnage). |
| **Orchestrateur** | Apache Airflow 3.3 | Outil vu en cours ; permet une planification horaire fiable (cron `0 * * * *`), un historique de runs consultable dans l'UI (preuve d'exécution), des retries automatiques (1 retry, 5 min) et un découpage clair du pipeline en tâches (`extract`, `save_raw`, `transform`, `load`, `alert`). |
| **Stockage brut (`raw/`)** | Fichiers CSV locaux, 1 fichier par ville et par appel | Conforme à la règle du contrat de données : zone brute intouchable, servant de sauvegarde permettant de rejouer intégralement `clean/` et le warehouse. |
| **Stockage propre (`clean/`)** | 1 fichier CSV unique, reconstruit à chaque run | Répond au contrat de données : toutes villes réunies, triées chronologiquement, dédupliquées sur `(city_name, timestamp)`. |
| **Data Warehouse** | PostgreSQL 16 | Base relationnelle robuste, gratuite, bien supportée par SQLAlchemy ; les contraintes `UNIQUE`/`FOREIGN KEY` et `ON CONFLICT DO NOTHING` garantissent l'idempotence des chargements (aucun doublon même en cas de ré-exécution). |
| **Modélisation** | Schéma en flocon (6 tables) | La dimension polluant se normalise naturellement en `dim_pollutant` + `dim_pollutant_category` (les polluants se regroupent par catégorie : indices AQI, particules, gaz), ce qui évite la redondance qu'imposerait un schéma en étoile pur ; respecte la règle « pas de mesure dans les dimensions, pas de colonne descriptive dans les faits ». |
| **Chargement** | SQLAlchemy + `INSERT ... ON CONFLICT DO NOTHING`, par lots de 5000 lignes | Chargement idempotent et rejouable (important pour le backfill et les reprises après erreur), performant même sur de gros volumes historiques. |
| **Qualité des données** | Module `quality.py` (valeurs manquantes, doublons, bornes physiques, types) exécuté à chaque étape clé (`extract`, `raw`, `fact`) | Trace un rapport de qualité à chaque étape du pipeline sans bloquer l'exécution, avec logs explicites en cas d'anomalie. |
| **Alertes** | Email SMTP si AQI ≥ seuil configurable, avec cooldown de 6h | Fonctionnalité additionnelle : notifie en cas de pic de pollution sans spammer, en interrogeant l'historique déjà chargé en base. |
| **Secrets** | Variables d'environnement via `.env` (Pydantic-Settings), `.env` exclu du dépôt (`.gitignore`) | Aucune clé/API/mot de passe en dur dans le code ni dans l'historique Git, conformément à la règle du projet. |
| **Conteneurisation** | Docker Compose (PostgreSQL + Airflow API server + scheduler + dag-processor) | Déploiement reproductible en une commande (`docker compose up -d`), isolation des services, redémarrage automatique (`restart: unless-stopped`) pour garantir la continuité du pipeline après la remise. |
| **Hébergement** | Oracle Cloud Always Free Tier (VM AMD/ARM) | Solution gratuite et pérenne permettant au pipeline de continuer à tourner après la remise, condition explicitement demandée pour que le cours IA1 puisse consommer les données en continu. |
| **Tests** | `pytest` sur `extract`, `transform`, `quality`, `alert` | Sécurise les transformations critiques (construction du schéma en flocon, calcul des dépassements de seuil OMS) contre les régressions. |

## Choix de modélisation : étoile vs flocon

Le schéma **flocon** a été retenu plutôt que l'étoile pure car la dimension polluant présente une hiérarchie naturelle (catégorie de polluant → polluant), extraite dans une table séparée `dim_pollutant_category`. Cela normalise l'information de catégorie (évite sa répétition dans `dim_pollutant`) sans complexifier excessivement les jointures, puisque le nombre de polluants reste faible (8).

## Cohérence des données

Nombre de lignes attendu dans `fact_air_quality` ≈ nombre de villes (5) × nombre d'heures couvertes × nombre de polluants (8), les écarts éventuels (valeurs manquantes de l'API, coupures réseau) étant tracés par le module `quality.py` et documentés dans le README.
