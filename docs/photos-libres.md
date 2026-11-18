# Photos d’illustration (libres de droits)

Les biens de démonstration n’ont pas de vraies photos. Pour éviter 344 cartes identiques,
`scripts/illustration_photos.py` attribue à chaque bien sans photo une image de sa catégorie,
choisie parmi celles-ci. Elles passent par le même stockage qu’un envoi depuis le back-office
(WebP redimensionné + vignette) et leur texte alternatif commence par « Photo d’illustration » :
le visiteur sait qu’il ne s’agit pas du bien lui-même.

Toutes viennent de Wikimedia Commons et sont dans le **domaine public** ou sous licence
**CC0 1.0** (aucune attribution obligatoire, usage commercial autorisé). Les auteurs sont
tout de même cités ci-dessous. Fichiers : `scripts/stock_photos/` (recadrés à 1 600 px
au plus, recompressés en WebP ; détails dans `manifest.json`).

Commandes (dans le conteneur `app`) :

```sh
python -m scripts.illustration_photos add      # une photo par bien, trois pour un bien sur quatre
python -m scripts.illustration_photos remove   # retire uniquement ces photos (fichiers et lignes)
```

Elles sont ajoutées automatiquement au démarrage quand `SEED_ON_STARTUP=true`.

## Appartement

| Fichier | Image d’origine | Auteur | Licence |
|---|---|---|---|
| `apartment-1.webp` | [At Home (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:At_Home_(Unsplash).jpg) | Naomi Hébert naomish | CC0 |
| `apartment-2.webp` | [Budapest Apartment (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Budapest_Apartment_(Unsplash).jpg) | Justin Schüler blacktakeover | CC0 |
| `apartment-3.webp` | [Home Sweet Home Pt. 4 (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Home_Sweet_Home_Pt._4_(Unsplash).jpg) | Kari Shea karishea | CC0 |
| `apartment-4.webp` | [Blue white kitchen interior (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Blue_white_kitchen_interior_(Unsplash).jpg) | NeONBRAND neonbrand | CC0 |

## Maison

| Fichier | Image d’origine | Auteur | Licence |
|---|---|---|---|
| `house-1.webp` | [Stone huts at the Tulogo pasture 01.jpg](https://commons.wikimedia.org/wiki/File:Stone_huts_at_the_Tulogo_pasture_01.jpg) | Ajznponar | CC0 |
| `house-2.webp` | [Stone huts at the Tulogo pasture 02.jpg](https://commons.wikimedia.org/wiki/File:Stone_huts_at_the_Tulogo_pasture_02.jpg) | Ajznponar | CC0 |
| `house-3.webp` | [Stone huts at the Tulogo pasture 03.jpg](https://commons.wikimedia.org/wiki/File:Stone_huts_at_the_Tulogo_pasture_03.jpg) | Ajznponar | CC0 |
| `house-4.webp` | [South facade - Packwood House - Warwickshire, England - DSC08555.jpg](https://commons.wikimedia.org/wiki/File:South_facade_-_Packwood_House_-_Warwickshire,_England_-_DSC08555.jpg) | Daderot | Public domain |

## Terrain

| Fichier | Image d’origine | Auteur | Licence |
|---|---|---|---|
| `land-1.webp` | [Top view of lavender flowers (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Top_view_of_lavender_flowers_(Unsplash).jpg) | Noah Baslé noahbasle | CC0 |
| `land-2.webp` | [Olive grove in HaNundalet (54) memorial7619.jpg](https://commons.wikimedia.org/wiki/File:Olive_grove_in_HaNundalet_(54)_memorial7619.jpg) | יעקב | CC0 |
| `land-3.webp` | [Olive grove in HaNundalet (54) memorial7622.jpg](https://commons.wikimedia.org/wiki/File:Olive_grove_in_HaNundalet_(54)_memorial7622.jpg) | יעקב | CC0 |
| `land-4.webp` | [Olive grove in HaNundalet (54) memorial7625.jpg](https://commons.wikimedia.org/wiki/File:Olive_grove_in_HaNundalet_(54)_memorial7625.jpg) | יעקב | CC0 |

## Bureaux

| Fichier | Image d’origine | Auteur | Licence |
|---|---|---|---|
| `office-1.webp` | [120 E 8th St, Los Angeles, United States (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:120_E_8th_St,_Los_Angeles,_United_States_(Unsplash).jpg) | Breather breather | CC0 |
| `office-2.webp` | [Chairs in a meeting room (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Chairs_in_a_meeting_room_(Unsplash).jpg) | Breather breather | CC0 |
| `office-3.webp` | [My working space (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:My_working_space_(Unsplash).jpg) | Vadim Sherbakov madebyvadim | CC0 |
| `office-4.webp` | [Casual Meeting Room (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Casual_Meeting_Room_(Unsplash).jpg) | Dan Gold danielcgold | CC0 |

## Local commercial

| Fichier | Image d’origine | Auteur | Licence |
|---|---|---|---|
| `retail-1.webp` | [Copenhagen, Denmark (Unsplash VL4FDP1AYU0).jpg](https://commons.wikimedia.org/wiki/File:Copenhagen,_Denmark_(Unsplash_VL4FDP1AYU0).jpg) | Steinar Engeland steinart | CC0 |
| `retail-2.webp` | [Empty coffee shop interior with wooden table and water skis.jpg](https://commons.wikimedia.org/wiki/File:Empty_coffee_shop_interior_with_wooden_table_and_water_skis.jpg) | Drew Coffman | CC0 |
| `retail-3.webp` | [Vintage apparel store interior (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Vintage_apparel_store_interior_(Unsplash).jpg) | Clark Street Mercantile mercantile | CC0 |
| `retail-4.webp` | [Bar façade with a bicycle (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Bar_fa%C3%A7ade_with_a_bicycle_(Unsplash).jpg) | photo-nic.co.uk nic chiro | CC0 |

## Entrepôt

| Fichier | Image d’origine | Auteur | Licence |
|---|---|---|---|
| `warehouse-1.webp` | [Backplate – Empty Warehouse 01 DSC 0026 RAW-Export (Sergej Majboroda via Poly Haven).png](https://commons.wikimedia.org/wiki/File:Backplate_%E2%80%93_Empty_Warehouse_01_DSC_0026_RAW-Export_(Sergej_Majboroda_via_Poly_Haven).png) | Sergej Majboroda | CC0 |
| `warehouse-2.webp` | [Backplate – Empty Warehouse 01 DSC 0044 RAW-Export (Sergej Majboroda via Poly Haven).png](https://commons.wikimedia.org/wiki/File:Backplate_%E2%80%93_Empty_Warehouse_01_DSC_0044_RAW-Export_(Sergej_Majboroda_via_Poly_Haven).png) | Sergej Majboroda | CC0 |
| `warehouse-3.webp` | [Backplate – Empty Warehouse 01 DSC 0074 RAW-Export (Sergej Majboroda via Poly Haven).png](https://commons.wikimedia.org/wiki/File:Backplate_%E2%80%93_Empty_Warehouse_01_DSC_0074_RAW-Export_(Sergej_Majboroda_via_Poly_Haven).png) | Sergej Majboroda | CC0 |
| `warehouse-4.webp` | [Backplate – Empty Warehouse 01 DSC 0941 RAW-Export (Sergej Majboroda via Poly Haven).png](https://commons.wikimedia.org/wiki/File:Backplate_%E2%80%93_Empty_Warehouse_01_DSC_0941_RAW-Export_(Sergej_Majboroda_via_Poly_Haven).png) | Sergej Majboroda | CC0 |
