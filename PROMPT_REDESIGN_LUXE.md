# Prompt — Refonte de la DA Ymmo (immobilier haut de gamme)

> À coller tel quel dans Claude Code, à la racine du projet `Ymmo`.

---

Tu es directeur artistique et développeur front senior, spécialisé dans l'immobilier de prestige. Refonds entièrement l'identité visuelle du site Ymmo pour qu'il ait l'air d'une agence haut de gamme crédible, et plus d'un projet étudiant.

## Contexte technique (à respecter)

- Stack : FastAPI + templates **Jinja2** côté serveur. **Pas** de framework JS, **pas** de Tailwind, **pas** de CDN : tout reste en CSS/JS vanilla et en fichiers locaux.
- Fichiers concernés :
  - `app/static/css/main.css` : design system (tokens primitifs → tokens sémantiques), à réécrire
  - `app/static/js/app.js` : petites interactions seulement
  - `app/templates/base.html` : header, nav, footer
  - `app/templates/macros.html` : `property_card`, `media`, `favorite_button`, badges…
  - `app/templates/index.html`, `properties/list.html`, `properties/detail.html`, `estimate.html`, `auth/*.html`, `client/dashboard.html`, `staff/*.html`, `analytics/dashboard.html`, `error.html`
- **Ne modifie aucune logique** : routes, noms de variables Jinja, attributs `name` des formulaires, `action`/`method`, blocs `{% %}`, attributs ARIA et `aria-current`. Tu ne changes que la structure HTML de présentation, les classes et le CSS.
- Garde le niveau d'accessibilité **WCAG 2.1 AA** : contrastes ≥ 4.5:1 pour le texte, focus visible, cibles de 44 px, skip-link, `prefers-reduced-motion` respecté.
- Mobile-first, puis responsive jusqu'à 1440 px et plus.
- Avant de changer la palette, vérifie dans les PDF du sujet (`ProjetFilRB2-2.pdf`, `UF_INFRA + DEV_B2-1.pdf`) si les couleurs crème (#f5f0e6), kaki (#5f6b3c) et brun (#4a3728) sont **imposées**. Si oui, garde-les comme base et monte en gamme par la typo, l'espace et la mise en page plutôt que par la couleur.

## Références visuelles

Inspire-toi de l'esprit (pas de copie) de : **Barnes**, **Émile Garcin**, **Sotheby's International Realty**, **Knight Frank**, **Daniel Féau**, **The Modern House**, **Aman / Six Senses** (pour le côté hôtellerie de luxe).

Ce qu'ils ont en commun, et que je veux retrouver :
1. **L'image d'abord** : photos très grandes, plein cadre, peu de texte par-dessus.
2. **Beaucoup d'espace** : marges généreuses, sections de 120 à 160 px de haut en desktop, rythme lent.
3. **Une typo éditoriale** : grand serif fin pour les titres, sans-serif sobre et petit pour le reste, petites capitales espacées pour les labels.
4. **Une palette retenue** : 2 ou 3 couleurs au maximum, un accent rare et précieux (laiton/or sourd, ou le kaki existant si imposé).
5. **Aucun effet « SaaS »** : pas de dégradés criards, pas d'ombres lourdes, pas de coins très arrondis, pas d'emojis, pas de glassmorphism.
6. **Des micro-interactions discrètes** : zoom lent sur l'image au survol (scale 1.03, 600 ms), soulignés qui se dessinent, fondus à l'apparition au scroll.

## Direction artistique attendue

**Palette** (à adapter si les couleurs sont imposées) :
- Fond : ivoire chaud `#F7F4EE`, surfaces alternées `#EFEAE1`
- Encre : quasi-noir chaud `#1C1A17` pour les titres, `#3B3631` pour le texte, `#7A7268` pour le secondaire
- Accent : laiton sourd `#9C7A4B` (vérifie le contraste ; utilise une variante plus foncée pour le texte)
- Une section sombre de contraste (footer, bandeau « Estimer ») : `#1C1A17` avec texte ivoire

**Typographie** :
- Titres : garde **Newsreader** (déjà en local), en graisse 300 à 400, très grand (hero entre `clamp(2.75rem, 6vw, 5.5rem)`), interlignage serré, `letter-spacing: -0.02em`
- Texte : **Public Sans** en 400, 16 à 17 px, interlignage 1.65
- Labels / sur-titres : petites capitales en 11 à 12 px, `letter-spacing: 0.18em`, couleur accent
- Prix : serif, chiffres tabulaires, mis en valeur mais sans gras excessif

**Formes** : rayon de 0 à 2 px, filets fins de 1 px, aucune ombre portée (ou une ombre très diffuse au survol seulement).

## Page par page

### Header (`base.html`)
- Transparent par-dessus le hero de l'accueil, puis fond ivoire avec filet bas une fois qu'on scrolle (classe ajoutée en JS)
- Logo « YMMO » en serif avec un espacement large, sous-titre « Immobilier » en petites capitales
- Navigation centrée ou alignée à droite, liens en petites capitales espacées, soulignement animé
- CTA « Estimer mon bien » en bouton contour fin
- Mobile : menu plein écran ivoire, liens en grand serif

### Accueil (`index.html`)
1. **Hero** en plein écran (`min-height: 90svh`), image de fond avec un léger voile sombre en dégradé vers le bas, titre serif blanc aligné en bas à gauche, sur-titre « Réseau immobilier · 12 agences en France »
2. **Barre de recherche** qui chevauche le bas du hero : une seule ligne horizontale élégante (ville | type | budget | pièces | bouton), séparateurs verticaux fins, pas de « carte » massive
3. **Nouveautés** : en-tête de section avec sur-titre + grand titre serif + lien « Voir tous les biens → », grille asymétrique (1 grande carte et 2 plus petites, ou un carrousel horizontal avec scroll-snap)
4. **« Pourquoi Ymmo »** devient un bloc éditorial : grande image d'un côté, texte de l'autre, avec 3 engagements numérotés (01, 02, 03) en serif
5. **Bandeau sombre « Estimez votre bien »** avec un grand titre et un CTA
6. **Agences** : liste typographique élégante sur 2 ou 3 colonnes (ville en serif + lien), sans aspect de tableau
7. **Footer** sombre, sur 4 colonnes, grand logo, filets fins, mentions discrètes

### Carte bien (`macros.html` → `property_card`)
- Image au ratio 4:5 ou 3:2, sans bordure, zoom lent au survol
- Badge de statut en petites capitales sur fond ivoire, en haut à gauche
- Favori : cœur fin en haut à droite, sur un cercle ivoire translucide
- Sous l'image : ville en petites capitales (accent) → titre en serif → caractéristiques séparées par des « · » → prix en serif aligné à droite ou dessous
- Placeholder sans photo : fond `#EFEAE1` avec l'icône de catégorie en trait fin et le type en petites capitales

### Liste des biens (`properties/list.html`)
- Filtres dans une barre horizontale sticky épurée (ou un panneau latéral sur desktop), selects stylés sans l'apparence native
- Compteur de résultats en serif (« 128 biens »), tri à droite
- Grille de 3 colonnes en desktop avec un grand espacement (48 px)

### Fiche bien (`properties/detail.html`)
- Galerie en mosaïque (1 grande + 4 petites), bouton « Voir les N photos »
- En-tête : ville en sur-titre, titre en grand serif, prix bien visible
- Colonne de droite sticky : prix, prix/m², caractéristiques clés, carte agent avec CTA « Demander une visite »
- Caractéristiques en grille d'icônes fines + libellés en petites capitales
- Description en colonne de lecture étroite (65ch)

### Formulaires (estimation, connexion, inscription)
- Champs avec seulement un filet du bas (style « underline »), label flottant ou label en petites capitales au-dessus
- Mise en page en 2 colonnes : image d'ambiance à gauche, formulaire à droite (desktop)

### Espaces client / staff / analytics
- Même design system, mais plus dense : tableaux avec filets fins, en-têtes en petites capitales, chiffres en serif tabulaire, cartes KPI sobres. Ça doit rester fonctionnel.

## Méthode

1. Lis tous les templates et `main.css` pour inventorier les classes utilisées
2. Réécris les **tokens** (`:root`) : palette, échelle typo fluide avec `clamp()`, espacements jusqu'à 10rem, une durée et un easing (`cubic-bezier(.2,.7,.2,1)`)
3. Réécris les composants dans cet ordre : base → header/footer → boutons/formulaires → carte bien → sections de l'accueil → liste → fiche → dashboards
4. Adapte le HTML des templates seulement là où la mise en page l'exige
5. Ajoute dans `app.js` : header au scroll, apparition au scroll via `IntersectionObserver` (désactivée si `prefers-reduced-motion`)
6. Lance l'app et vérifie chaque page en **375 px, 768 px et 1440 px** ; corrige les débordements
7. Vérifie les contrastes de chaque couple texte/fond et note les ratios en commentaire dans les tokens
8. Lance `pytest` pour t'assurer que rien n'a cassé

## Critère de réussite

Une personne qui voit la page d'accueil pendant 3 secondes doit penser « agence de prestige », pas « template ». Si une section ressemble à un dashboard générique ou à une landing SaaS, recommence-la.
