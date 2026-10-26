# PSIE — Cahier des charges et architecture (version 0.1, à valider)

> **Statut : proposition de travail.** Rien n'est encore développé. Ce document sert de base de
> discussion : on le corrige ensemble, on tranche les points marqués **[À VALIDER]**, puis on
> démarre le développement par phases.
>
> PSIE = *Plate-forme des Structures Islamiques de l'Éducation*. Elle regroupe les **faîtières**
> (fédérations / ligues / associations nationales) des structures islamiques d'éducation. La
> LECIM en est **membre fondateur**. Les faîtières cotisent chaque année, et ponctuellement en
> cas d'exception (appel de fonds exceptionnel).

---

## 1. Ce que j'ai compris du modèle LECIM

La LECIM fonctionne sur ce schéma, que la PSIE reproduit **un niveau au-dessus** :

| Niveau | LECIM (existant) | PSIE (à construire) |
|---|---|---|
| Organisation faîtière | LECIM | **PSIE** |
| Membres cotisants | Établissements (écoles, madrassas) | **Faîtières** (dont la LECIM, fondatrice) |
| Cotisation | Annuelle, barème fixe (7 500 / 20 000 FCFA selon statut) + droit d'adhésion unique (12 000 FCFA) | Annuelle **+ exceptionnelle** (montants à définir) |
| Instances | Bureau Exécutif National, délégations régionales, conseil d'administration | Bureau / secrétariat PSIE, Assemblée Générale, commissions |
| Portails | Admin/BEN, délégation, établissement | Admin/Bureau PSIE, **portail faîtière** |
| Vitrine | Site statique + API publique | Site vitrine PSIE |
| Preuves | Cartes et attestations PDF avec QR code vérifiable | Certificat d'adhésion, attestation de cotisation, reçus |

Ce que la LECIM a déjà et qu'on **réutilise** (code, pas à réinventer) : authentification et
rôles, 2FA par e-mail, journal d'audit, circuit demande d'adhésion → validation → certificat,
gestion des cotisations par année, finances (recettes, dépenses, budget prévisionnel, rapports),
réunions / présences / PV, courrier, newsletter, PWA, sauvegardes chiffrées hors-site,
import Excel, planificateur de relances.

Ce que la LECIM **n'a pas** et qu'il faut **ajouter** pour la PSIE :

1. **Cotisation exceptionnelle** (appel de fonds ponctuel, avec motif, échéance, montant par faîtière).
2. **Paiements multiples par échéance** (la LECIM n'a qu'un `montant_paye` global par année : insuffisant pour des versements échelonnés et des reçus numérotés).
3. **Assemblée Générale** avec convocation, quorum, résolutions et votes.
4. **Catégories de membres** (fondateur / adhérent / observateur) avec droits associés.
5. **Représentants** : chaque faîtière désigne des délégués officiels auprès de la PSIE.

---

## 2. Décision d'architecture n°1 : projet séparé

**Recommandation : créer un dépôt et un déploiement distincts (`projet-psie`), démarrés à partir
du code de la LECIM, et non ajouter la PSIE dans la base LECIM.**

| Option | Avantages | Inconvénients |
|---|---|---|
| A. Même application, multi-tenant | Un seul code | La LECIM est *membre* de la PSIE : mélanger leurs données crée des risques de fuite et un couplage juridique/organisationnel. Un bug LECIM affecterait la PSIE. |
| **B. Projet séparé, code de base copié (recommandé)** | Données et accès totalement isolés ; chaque entité a son rythme, son domaine, ses sauvegardes ; on garde tout ce qui marche | Duplication initiale ; les correctifs de sécurité communs se reportent à la main |
| C. Bibliothèque commune extraite | Zéro duplication | Surdimensionné pour un projet amateur à ce stade |

On part sur **B**, et on pourra extraire un socle commun plus tard si les deux projets durent.
La PSIE aura sa propre base PostgreSQL, son propre `.env`, son domaine, ses sauvegardes.

**[À VALIDER]** Option B retenue ?

---

## 3. Acteurs et rôles

| Rôle | Portée | Actions principales |
|---|---|---|
| **Super-admin PSIE** | Tout | Paramétrage, comptes, barèmes, audit |
| **Bureau PSIE** (président, SG, …) | Gouvernance | Valider les adhésions, convoquer les AG, suivre les cotisations |
| **Trésorier PSIE** | Finances | Enregistrer les paiements, émettre les reçus, lancer les appels exceptionnels, rapports financiers (2FA obligatoire) |
| **Secrétariat PSIE** | Administratif | Courrier, PV, documents, annuaire des faîtières |
| **Représentant de faîtière** (titulaire) | Sa faîtière | Voir sa situation, ses échéances, ses reçus, ses convocations, voter si l'AG est dématérialisée |
| **Délégué de faîtière** (secondaire) | Rubriques cochées | Accès limité (même logique que « secrétaire d'établissement » dans la LECIM) |
| **Observateur** | Lecture seule | Commissaire aux comptes, audit |
| **Public** | Vitrine | Lire les actualités, vérifier un certificat via QR code, demander l'adhésion |

Les rôles s'appuient sur le modèle déjà éprouvé de la LECIM : `access_level` + `allowed_modules`
(liste de modules cochés par l'admin) + rattachement d'un compte à une faîtière.

---

## 4. Modules fonctionnels

### 4.1 Annuaire des faîtières
- Fiche : nom, sigle, date de création, statut juridique, siège, contacts, logo, représentants légaux.
- **Catégorie** : `fondateur` | `adhérent` | `observateur` **[À VALIDER : quelles catégories exactement ?]**.
- Statut : `active` | `suspendue` | `radiée`.
- Informations de couverture (indicatives) : nombre de structures affiliées, régions, effectifs
  d'élèves — saisis ou mis à jour chaque année par la faîtière elle-même via son portail.
- Pièces : statuts, récépissé, PV de désignation des représentants.

### 4.2 Adhésion
Circuit repris de la LECIM : demande en ligne (code de suivi) → examen par le bureau → validation
→ **certificat d'adhésion PDF avec QR code** vérifiable publiquement.
- Droit d'adhésion unique **[À VALIDER : montant ?]**.
- Les faîtières fondatrices (dont la LECIM) sont créées directement, marquées `fondateur`.

### 4.3 Cotisations annuelles
- **Barème paramétrable** (table `bareme_cotisation`) plutôt que codé en dur comme dans la LECIM :
  montant par catégorie et par année, modifiable sans toucher au code.
  **[À VALIDER : montant unique ou barème selon la taille/catégorie de la faîtière ?]**
- À chaque ouverture d'année : génération **automatique** d'une échéance par faîtière active.
- Paiements partiels et échelonnés, plusieurs versements par échéance.
- Statut calculé : `à jour` | `partiel` | `en retard` | `impayé`.
- **Reçu PDF numéroté** (PSIE-REC-2026-0001) pour chaque versement, avec QR code de vérification.
- **Attestation de cotisation à jour** (utile pour justifier de son statut de membre).

### 4.4 Cotisations exceptionnelles (nouveauté)
Une cotisation exceptionnelle est un **appel de fonds** décidé par une instance (AG ou bureau).
- Création d'un **Appel** : intitulé, motif, décision à l'origine (référence PV), date limite.
- Mode de répartition : **montant égal pour toutes** | **montant par catégorie** | **montant libre par faîtière**.
  **[À VALIDER : quels modes sont réellement utilisés ?]**
- Génération automatique des échéances pour toutes les faîtières concernées (ou une sélection).
- Même mécanique de paiement / reçu / relance que la cotisation annuelle.
- Possibilité d'**exonérer** ou de **reporter** une faîtière (avec motif et trace d'audit).

### 4.5 Relances et notifications (automatisées)
- Rappel e-mail **J-30, J-7, J-0** avant échéance, puis relance hebdomadaire après retard.
- Notification à la faîtière à chaque paiement enregistré (reçu en pièce jointe).
- Alerte au trésorier : liste des retards chaque lundi.
- Notification push / PWA optionnelle (déjà présente dans la LECIM).

### 4.6 Gouvernance : Assemblées et réunions
- Réunions du bureau, commissions : convocation, présence, PV (repris de la LECIM).
- **Assemblée Générale** : convocation envoyée aux représentants, émargement (présentiel ou
  en ligne), **calcul du quorum**, résolutions, votes enregistrés.
- Règle de vote : 1 faîtière = 1 voix **[À VALIDER]**. Option : droit de vote suspendu si
  cotisation annuelle non à jour **[À VALIDER : prévu par les statuts ?]**.
- Visioconférence : le Jitsi auto-hébergé de la LECIM peut être réutilisé.

### 4.7 Finances de la PSIE
- Recettes : cotisations annuelles, exceptionnelles, droits d'adhésion, subventions, dons.
- Dépenses avec justificatifs, budget prévisionnel vs réalisé.
- **Rapports automatiques** : situation par faîtière, taux de recouvrement, bilan annuel (PDF/Excel).
- Journal d'audit sur toute écriture financière.

### 4.8 Documents, courrier, communication
- Bibliothèque de documents (statuts, règlement intérieur, PV, conventions), accès par rôle.
- Registre du courrier arrivée/départ.
- Actualités, galerie, newsletter, vitrine publique.

### 4.9 Tableau de bord
- Pour la PSIE : nombre de faîtières, taux de recouvrement de l'année, montants dus/encaissés,
  retards, appels exceptionnels en cours, prochaines réunions.
- Pour une faîtière : sa situation financière, ses prochaines échéances, ses documents.

### 4.10 Paiement en ligne (phase ultérieure)
Mobile money (Orange Money, MTN MoMo, Wave) via un agrégateur, avec rapprochement automatique.
Au départ : **enregistrement manuel** par le trésorier (virement, dépôt, espèces) avec
justificatif. **[À VALIDER : paiement en ligne souhaité à terme ?]**

---

## 5. Modèle de données (entités principales)

```mermaid
erDiagram
    FAITIERE ||--o{ COMPTE_UTILISATEUR : "a des comptes"
    FAITIERE ||--o{ REPRESENTANT : "désigne"
    FAITIERE ||--o{ ECHEANCE : "doit"
    BAREME_COTISATION ||--o{ ECHEANCE : "fixe le montant"
    APPEL_EXCEPTIONNEL ||--o{ ECHEANCE : "génère"
    ECHEANCE ||--o{ PAIEMENT : "reçoit"
    PAIEMENT ||--|| RECU : "produit"
    ASSEMBLEE ||--o{ PRESENCE_AG : "émargement"
    ASSEMBLEE ||--o{ RESOLUTION : "vote"
    RESOLUTION ||--o{ VOTE : "reçoit"
    FAITIERE ||--o{ PRESENCE_AG : "représentée par"
    FAITIERE ||--o{ VOTE : "vote"
    DEMANDE_ADHESION ||--o| FAITIERE : "devient"
```

Points clés :

- **`ECHEANCE`** est la table pivot : une ligne = « telle faîtière doit tel montant, pour tel
  motif (`annuelle` ou `exceptionnelle`), avant telle date ». Cotisations annuelles et appels
  exceptionnels partagent donc **la même mécanique** de paiement, reçu et relance.
- **`PAIEMENT`** : plusieurs par échéance (montant, date, mode, référence, justificatif,
  saisi par). Le solde et le statut de l'échéance sont **calculés** à partir des paiements,
  jamais saisis à la main.
- **`BAREME_COTISATION`** : (année, catégorie, montant) — modifiable sans redéploiement.
- **`APPEL_EXCEPTIONNEL`** : motif, décision d'origine, mode de répartition, date limite, statut.
- Les montants sont stockés en **entiers (FCFA)**, comme dans la LECIM, pas de décimales.
- Aucune suppression physique des écritures financières : annulation par contre-écriture
  (traçabilité).

---

## 6. Architecture technique

```
                 Internet
                    │
        ┌───────────┴────────────┐
        │  Reverse proxy HTTPS    │  (Caddy / Nginx + Let's Encrypt)
        └───────────┬────────────┘
   ┌────────────────┼──────────────────┐
   │                │                  │
 Vitrine         API + Portails      Jitsi (optionnel)
 statique        FastAPI (Python)
 (GitHub Pages)  ├─ /admin      Bureau PSIE / trésorerie
                 ├─ /faitiere   Portail faîtière
                 ├─ /api        Public (vérification QR, adhésion, actus)
                 └─ Scheduler   relances, génération des échéances,
                                sauvegardes, rapports
                    │
              PostgreSQL ──► sauvegarde chiffrée nocturne ──► dépôt privé hors-site
              Fichiers (justificatifs, PDF)
```

| Couche | Choix | Justification |
|---|---|---|
| Backend | **FastAPI + SQLAlchemy 2** | Identique à la LECIM : on réutilise le code et ce que vous connaissez déjà |
| Pages | **Jinja2** rendu serveur | Simple, peu de JavaScript, facile à maintenir seul |
| Base | **PostgreSQL 16** | Fiabilité pour la comptabilité, transactions |
| PDF | **fpdf2** (déjà utilisé) + QR codes | Reçus, certificats, attestations, rapports |
| Planification | **APScheduler** (déjà utilisé) | Relances, échéances, sauvegardes |
| Vitrine | Site statique | Même approche que la LECIM, coût nul |
| Conteneurs | **Docker Compose** | Démarrage en une commande |
| CI | **GitHub Actions** | Tests et lint automatiques à chaque push |
| Hébergement | VPS (comme la LECIM) | Un second conteneur suffit **[À VALIDER : même VPS ou autre ?]** |

### Sécurité (héritée de la LECIM et renforcée)
- Mots de passe bcrypt, JWT, **2FA par e-mail obligatoire** pour admin et trésorier.
- Verrouillage après échecs de connexion, limitation de débit, protection CSRF.
- **Cloisonnement strict** : un représentant de faîtière ne voit *jamais* les données d'une autre
  faîtière (filtre systématique par `faitiere_id` côté serveur, avec tests automatisés dédiés).
- Journal d'audit sur toute action sensible (paiement, exonération, changement de barème).
- Sauvegardes nocturnes chiffrées + copie hors-site + **test de restauration** automatisé.

---

## 7. Automatisations prévues

Ce que le système fait seul, sans intervention humaine :

| Automatisation | Déclencheur |
|---|---|
| Création des échéances de cotisation annuelle | Ouverture d'une nouvelle année |
| Création des échéances d'un appel exceptionnel | Validation de l'appel |
| Relances e-mail avant/après échéance | Planificateur quotidien |
| Génération et envoi du reçu PDF | Enregistrement d'un paiement |
| Résumé hebdomadaire des retards au trésorier | Chaque lundi |
| Rapport annuel de recouvrement (PDF + Excel) | Clôture d'année / à la demande |
| Calcul du quorum et du résultat des votes | Clôture d'un scrutin |
| Sauvegarde chiffrée + copie hors-site + test de restauration | Chaque nuit |
| Import en masse des faîtières depuis Excel | Script (modèle du `import_ecoles_excel.py` LECIM) |
| Tests + lint | À chaque push (GitHub Actions) |

---

## 8. Feuille de route par phases

| Phase | Contenu | Livrable utilisable |
|---|---|---|
| **0 — Cadrage** | Valider ce document, trancher les points ouverts, collecter statuts de la PSIE | Cahier des charges v1 |
| **1 — Socle + annuaire** | Nouveau dépôt, auth/rôles/2FA/audit repris, fiches faîtières, comptes représentants, import Excel, import de la LECIM comme fondatrice | Annuaire fonctionnel et sécurisé |
| **2 — Cotisations annuelles** | Barème, échéances auto, paiements, reçus PDF, attestations, relances, tableau de bord trésorier | **Cœur du besoin** : suivi des cotisations |
| **3 — Cotisations exceptionnelles** | Appels de fonds, répartition, exonérations/reports, relances | Gestion des cas d'exception |
| **4 — Adhésion + vitrine** | Demande d'adhésion en ligne, certificat à QR code, site vitrine, actualités | Image publique + nouvelles adhésions |
| **5 — Gouvernance** | Réunions, AG, quorum, résolutions, votes, PV, documents, courrier | Vie statutaire dématérialisée |
| **6 — Finances complètes + rapports** | Recettes/dépenses, budget prévisionnel, rapports automatiques | Redevabilité financière |
| **7 — Paiement mobile money** *(option)* | Agrégateur, rapprochement automatique | Encaissement en ligne |

Chaque phase est livrable seule. La **phase 2** est le premier moment où la PSIE tire une vraie
valeur de l'outil.

---

## 9. Points à valider ensemble

Réponses souhaitées, même approximatives, pour figer la version 1 :

1. **Projet séparé (option B)** : d'accord ?
2. **Faîtières membres** : combien environ aujourd'hui ? Quelles catégories (fondateur / adhérent / autres) ?
3. **Cotisation annuelle** : montant unique ou barème ? Quels montants ? Quelle période (année civile ou année scolaire) ?
4. **Droit d'adhésion** unique : existe-t-il pour la PSIE, et pour quel montant ?
5. **Cotisation exceptionnelle** : qui la décide (AG, bureau) ? Montant égal pour tous ou variable ?
6. **Sanctions en cas d'impayé** : suspension du droit de vote ? du statut de membre ? après combien de temps ?
7. **Assemblée Générale** : 1 faîtière = 1 voix ? Combien de représentants par faîtière ? Quorum fixé par les statuts ?
8. **Qui utilise l'outil au quotidien** côté PSIE (qui est trésorier, qui est secrétariat) ?
9. **Paiements** : virement, espèces, mobile money ? Faut-il le paiement en ligne à terme ?
10. **Langues** : français seul, ou français + arabe (la LECIM a déjà un dossier `ar/`) ?
11. **Nom de domaine** et **hébergement** : un domaine pour la PSIE existe-t-il déjà ? Même VPS que la LECIM ?
12. **Identité visuelle** : logo et charte graphique de la PSIE disponibles ?
13. **Statuts de la PSIE** : peux-tu me les fournir pour que je cale les règles (quorum, vote, sanctions, cotisations) sur le texte réel plutôt que sur des hypothèses ?

> Les montants et règles de la LECIM (7 500 / 20 000 FCFA, 12 000 FCFA, etc.) sont rappelés
> **uniquement comme référence** : rien ne dit qu'ils s'appliquent à la PSIE.
