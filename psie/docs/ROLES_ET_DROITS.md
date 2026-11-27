# Rôles et droits

Onze rôles (menu **Comptes**) ; chaque rôle a, par rubrique, un niveau **0 = aucun accès, 1 = lecture, 2 = lecture et modification**. L'administrateur règle tout dans **Accès par rubrique** (par rôle) et dans la fiche d'un compte (exception pour une personne).

| Rôle | Fonction | Par défaut (modification) | Lecture seule |
|---|---|---|---|
| `admin` | Administrateur de la plateforme | membres, adhésions, contenu du site, documents ; **comptes, droits, journal** | écoles |
| `den` | Directeur Exécutif National | membres, adhésions, écoles, documents | finances |
| `secretaire` | Secrétaire de la DEN | idem DEN | — |
| `finances` | Secrétaire aux finances | finances | membres, écoles, documents |
| `communication` | Information et Communication | contenu du site | documents |
| `formation`, `examens` | Secrétariats Formation / Examens | écoles | documents |
| `ressources` | Mobilisation des ressources | — | écoles, documents |
| `administrateur_ca` | Conseil d'Administration | — | membres, adhésions, finances, écoles, documents |
| `commissaire` | Commissaire aux comptes | — | finances, documents |
| `faitiere` | Représentant d'une faîtière | **uniquement sa faîtière** : infos, écoles, personnel, examens, bilans, cotisations, annonces, demandes | — |

L'administrateur technique n'a **pas** accès aux finances par défaut (séparation des fonctions).

Rubriques ajoutables dans la grille : membres, adhésions, finances, contenu du site, **écoles et suivi des faîtières**, **documents et courrier**, **formation**.
Par défaut, `formation` : modification pour le secrétariat Formation, le DEN et son secrétaire ; lecture pour Examens, CA et administrateur.

## Supervision : voir ce que font les comptes
Rubrique **supervision** (administrateur et DEN par défaut, réglable dans la grille) :
- **Lecture** : menu « Comptes et activité » — dernière connexion, dernière action, actions des 7 jours, et le détail de l'activité de chaque compte.
- **Modification** : en plus, « Voir son espace » ouvre l'interface **exactement comme le compte la voit**, en **lecture seule** (bandeau jaune, aucune modification possible, une heure maximum).
- Chaque consultation est inscrite au journal d'audit (action sensible, signalée à l'administrateur) ; ce que fait le superviseur pendant la consultation lui est attribué, jamais au compte consulté. Seul l'administrateur peut consulter l'espace d'un administrateur.

## Pouvoirs liés au rôle (non délégables par la grille)
- **Avis écrit sur une adhésion** : administrateur du CA (Statuts).
- **Dépenses** : double signature DEN + secrétaire aux finances, d'organisations d'origine différentes (Statuts art. 38).
- **Rapports** des commissaires aux comptes : rôle `commissaire`.
- **Conventions** : le CA donne son avis (`administrateur_ca`), le DEN signe (`den`) par signature électronique (code e-mail).

## Créer et gérer des comptes
- Un par un : menu **Comptes**. En lot : `deploy/creer-comptes.sh` (CSV, invitations par lien personnel).
- Aucun mot de passe n'est jamais transmis : lien valable 7 jours, à usage unique. Perdu : « Mot de passe oublié » sur la page de connexion, ou l'administrateur en fixe un nouveau dans **Comptes**.
- Un départ : **désactiver** le compte (jamais supprimer : l'historique reste attribué).

## Voir le portail d'un rôle
Dans **Supervision**, la section « Portails des secrétariats et des organes » ouvre le portail de chaque rôle (et de chaque faîtière) avec ses droits actuels, même si aucun compte n'existe encore. Lecture seule ; chaque ouverture est inscrite au journal d'audit.
