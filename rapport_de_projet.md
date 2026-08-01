# Rapport de projet — Surveillance de la qualité de l'air à Madagascar (AQI)

## 1. Présentation du projet

La pollution de l'air est un enjeu sanitaire majeur : l'Organisation mondiale de la santé (OMS) estime qu'elle est responsable de millions de décès prématurés chaque année, notamment dans les pays où les données de surveillance locales sont rares. À Madagascar, très peu de données de qualité de l'air sont publiées de façon continue et consolidée.

Ce projet a pour objectif de construire **un pipeline de données automatisé** qui collecte, transforme et charge l'indice de qualité de l'air (**AQI**) et les principaux polluants pour **cinq grandes villes de Madagascar** :

| Ville | Latitude | Longitude |
|---|---|---|
| Antananarivo | -18.8792 | 47.5079 |
| Toamasina | -18.149 | 49.4028 |
| Mahajanga | -15.7167 | 46.3167 |
| Fianarantsoa | -21.4333 | 47.0833 |
| Antsiranana | -12.3 | 49.2833 |

Les données proviennent de l'**API Open-Meteo Air Quality** (gratuite, sans clé), qui fournit l'indice AQI européen et américain ainsi que les concentrations de polluants (PM2.5, PM10, NO₂, O₃, SO₂, CO) à pas horaire, sur la période **juillet 2025 → août 2026** (397 jours).

**Livrables du projet :**
- Un pipeline ETL versionné sur GitHub (extraction → transformation → chargement → alertes), orchestré par Airflow.
- Un entrepôt de données PostgreSQL (Neon) en schéma en flocon.
- Le présent rapport et une vidéo de présentation (3 min).

## 2. Méthode de travail du groupe

L'équipe de **quatre membres** a adopté une organisation en **modules techniques** avec une répartition claire des responsabilités, validée par un workflow Git classique :

- **Branches par fonctionnalité** puis intégration via **pull request** (ex. PR n°1 `2leno/feature/data`) et merge par un relecteur.
- **Commits atomiques** (un changement logique par commit), messages descriptifs.
- **Revue croisée** : chaque module est relu et testé avant intégration.
- **Tests unitaires** (pytest) ajoutés en fin de cycle pour fiabiliser les modules (extract, transform, quality, alert).

**Outillage utilisé :**
- `uv` pour la gestion des dépendances (fichier `uv.lock` reproductible) + `requirements.txt`.
- **Airflow 3.3** pour l'orchestration (DAG horaire).
- **Docker Compose** pour l'infrastructure locale.
- **Neon** (PostgreSQL 16 managé, niveau gratuit) comme entrepôt de données.

**Chronologie des travaux (traçable dans l'historique Git) :**

| Date | Étape |
|---|---|
| 21/07/2026 | Initialisation du dépôt, package `data`, modules extract/load/quality/transform/alert |
| 22/07/2026 | Ajout du DAG Airflow |
| 30/07/2026 | Nettoyage README, ajout des tests unitaires + correction du bug `dtypes_check` |

## 3. Répartition des tâches

| Membre | Contribution (modules) | Preuve |
|---|---|---|
| **Lucas Andrianina ANDRIAMANGA** | Initialisation du dépôt, `scripts/backfill.py`, tests unitaires, README, coordination du rapport et de la vidéo | Commits `47e42d5`, `3d24a98`, `0e3abe1`, `6b8acf5`, `2a50e2d` |
| **Antsa** | Modules `extract`, `load`, `quality`, `transform`, `alert` | Commits `9b877ac`, `270846a`, `c2f28f0` |
| **Ny Lalaina** | Orchestration Airflow : DAG `air_quality_pipeline`, `dags/config.py` | Commit `9c510cd` |
| **Mbola (HAJARIMBOLA)** | Package `data/` (dimensions : villes, régions, catégories de polluants), merge des PR | Commits `38297c7`, `319ade1` |

*Note : le rapport et la vidéo ne figurent pas dans le dépôt Git ; la répartition des modules ETL est, elle, directement traçable par les commits.*

## 4. Choix techniques justifiés

| Choix | Justification |
|---|---|
| **Open-Meteo Air Quality API** | Gratuite, sans clé API, couvre les 5 villes, fournit directement l'indice `european_aqi` et `us_aqi` (pas de calcul complexe côté pipeline). Alternatives (OpenAQ, WAQI) plus contraignantes ou limitées. |
| **PostgreSQL (Neon)** | Base managée gratuite, accessible depuis Airflow, standard SQL. |
| **Schéma en flocon (6 tables)** | Normalisation des dimensions (`dim_region`, `dim_city`, `dim_pollutant_category`, `dim_pollutant`, `dim_date`) autour d'une table de faits (`fact_air_quality`) → pas de redondance, requêtes d'agrégation fiables. |
| **Airflow 3.3** | Orchestration déclarative (DAG), planning horaire (`0 * * * *`), rétries et gestion des échecs, suivi visuel dans l'UI. |
| **Contrôle qualité intégré** | Bornes physiques (`PHYSICAL_RANGES`), détection des valeurs manquantes / doublons / hors bornes, audit en 3 étapes. |
| **Seuils OMS** | Seuils par polluant stockés dans `POLLUTANT_META` (PM2.5 = 15, PM10 = 45, NO₂ = 25, O₃ = 100, SO₂ = 40, CO = 10000 µg/m³) → colonne `exceeds_who_threshold`. |
| **Alertes email** | Avertissement automatique quand l'AQI ≥ 4 (seuil `european_aqi`), avec **cooldown de 6 h** pour éviter les notifications répétitives. |
| **uv + uv.lock** | Reproductibilité des environnements (`pyproject.toml`, `uv.lock`), cohérence entre les postes et le CI. |

## 5. Difficultés rencontrées et résolutions

### Difficultés techniques (résolues)

- **Erreurs API par ville** : une ville en erreur pouvait bloquer toute l'extraction → `try/except` par ville avec **continuation** (une ville en échec n'empêche pas les autres).
- **Conflits de clé primaire DAG / backfill** : doublons potentiels entre l'historisation par Airflow et le script de backfill → **`date_id` déterministe** (heures écoulées depuis une date de référence).
- **Bug `dtypes_check`** : erreur de vérification des types découverte lors des tests → **corrigée** dans le commit d'ajout des tests unitaires.
- **Corrélation réelle ≠ exemple du cours** : la corrélation PM2.5 ↔ AQI observée (0,26) est bien plus faible que l'exemple du cours (0,86) → discussion sur la différence entre données simulées et données réelles, et justification de l'analyse multi-polluants.

## 6. Résultats et livrables

**Données chargées :**
- **47 560** mesures horaires, **5 villes**, **397 jours** (07/2025 → 08/2026), 8 paramètres par relevé.
- **AQI moyen (indice européen) : 20,45** — Antananarivo la plus exposée, Antsiranana la plus saine.
- **1 566 dépassements OMS** : PM2.5 (1 236), Ozone (315), PM10 (15) — mettant en évidence les pics de particules fines en saison sèche.

**Autres livrables :** pipeline ETL versionné (GitHub), entrepôt PostgreSQL (Neon), rapport, vidéo de présentation.

## 7. Limites et perspectives

**Limites :**
- Source de données unique (Open-Meteo) : pas de croisement avec d'autres capteurs.
- Les seuils OMS appliqués sont des moyennes 24 h ; leur comparaison à des relevés **horaires** est une approximation.
- Cooldown d'alerte fixé à 6 h (pas de notification en quasi temps réel).

**Perspectives :**
- Prévision de l'AQI par apprentissage automatique (séries temporelles).
- Extension à d'autres villes et ajout de sources de données (capteurs IoT).
- Alertes multi-canaux (SMS, mobile) et seuils configurés par ville.
- Élargissement de l'historique pour une analyse climatique de long terme.
