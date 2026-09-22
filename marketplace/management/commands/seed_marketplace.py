from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from marketplace.models import BoostPlan, Category, City, EnterpriseAdPlan, Neighborhood, PlatformSettings


# -----------------------------------------------------------------------------
# Marché Local / Cameroon production seed
# -----------------------------------------------------------------------------
# Important data model note:
# - City is used for marketplace-friendly urban locations.
# - Neighborhood is used for named quartiers where a reliable list is available.
# - Smaller urban locations receive neutral "Centre-ville" / "Autre quartier"
#   fallbacks rather than fabricated neighborhood names.
# - The command NEVER deletes existing categories/cities/neighborhoods, because
#   doing so could orphan or damage existing listings.
# -----------------------------------------------------------------------------

FALLBACK_NEIGHBORHOODS = ["Centre-ville", "Autre quartier"]

CATEGORY_TREE = {
    "Immobilier": [
        "Vente maison & appartement", "Location maison & appartement",
        "Studios & chambres", "Chambres meublées", "Appartements meublés",
        "Villas & maisons", "Duplex & triplex", "Terrains résidentiels",
        "Terrains agricoles", "Bureaux & espaces professionnels", "Locaux commerciaux",
        "Boutiques & magasins", "Entrepôts & magasins", "Colocation",
        "Immobilier commercial", "Hôtels & auberges à vendre", "Promotion immobilière",
        "Gestion & syndic immobilier", "Parking & garage", "Autres immobilier",
    ],
    "Véhicules": [
        "Voitures", "SUV & 4x4", "Berlines", "Pick-up", "Minibus & bus",
        "Motos & scooters", "Tricycles", "Camions & poids lourds", "Camions & utilitaires",
        "Véhicules de chantier", "Pièces automobiles", "Pièces motos", "Pneus", "Batteries",
        "Huiles & lubrifiants", "Accessoires automobiles", "Accessoires motos",
        "Location de véhicules", "Chauffeur avec véhicule", "Autres véhicules",
    ],
    "Téléphones & Informatique": [
        "Téléphones & smartphones", "iPhone", "Samsung", "Tecno", "Infinix", "Itel",
        "Oppo & Xiaomi", "Téléphones classiques", "Ordinateurs portables", "Ordinateurs de bureau",
        "MacBook", "Tablettes", "Télévisions", "Audio & enceintes", "Consoles & jeux vidéo",
        "Imprimantes & scanners", "Accessoires téléphone", "Chargeurs & câbles", "Power banks",
        "Composants informatiques", "Réseaux & Wi-Fi", "Caméras & vidéosurveillance",
        "Logiciels & licences", "Réparation téléphone", "Maintenance informatique", "Autres informatique",
    ],
    "Maison & Électroménager": [
        "Canapés & fauteuils", "Lits & matelas", "Armoires & rangements", "Tables & chaises",
        "Bureaux & meubles de travail", "Électroménager", "Réfrigérateurs & congélateurs",
        "Cuisinières & fours", "Mixeurs & petits appareils", "Ventilateurs & climatiseurs",
        "Cuisine & vaisselle", "Rideaux & linge de maison", "Décoration", "Éclairage",
        "Jardin & extérieur", "Matériel de bricolage", "Groupes électrogènes & énergie",
        "Panneaux solaires", "Autres maison",
    ],
    "Mode & Beauté": [
        "Vêtements femme", "Vêtements homme", "Vêtements enfants", "Robes & ensembles",
        "Costumes & tenues professionnelles", "Chaussures femme", "Chaussures homme",
        "Chaussures enfants", "Sacs & bagages", "Bijoux & accessoires de mode", "Montres",
        "Cosmétiques", "Parfums", "Soins capillaires", "Coiffure & barber", "Esthétique & maquillage",
        "Mode africaine & tissus", "Couture & retouche", "Autres mode & beauté",
    ],
    "Services": [
        "Plomberie", "Électricité", "Peinture & finition", "Maçonnerie", "Carrelage & sanitaire",
        "Menuiserie bois", "Aluminium & vitrerie", "Soudure & métallerie", "Ménage & nettoyage",
        "Lavage automobile", "Désinfection & entretien", "Réparation téléphone", "Informatique & réseaux",
        "Développement web", "Développement logiciel", "Graphisme & design", "Community management",
        "Marketing & communication", "Photographie", "Vidéo & montage", "Couture & retouche",
        "Coiffure & barber", "Beauté & esthétique", "Livraison & courses", "Déménagement", "Transport",
        "Taxi & moto-taxi", "Chauffeur privé", "Sécurité & gardiennage", "Cours particuliers",
        "Formation professionnelle", "Traduction & interprétation", "Rédaction & correction",
        "Maintenance & dépannage", "DJ & animation", "Sonorisation", "Cuisine & service traiteur",
        "Serveur & service événementiel", "Décoration événementielle", "Organisation d'événements",
        "Services Mobile Money", "Conseil & accompagnement", "Assistance administrative",
        "Comptabilité & fiscalité", "Services aux entreprises", "Autres services",
    ],
    "Emploi & Missions": [
        "Emploi à temps plein", "Emploi à temps partiel", "Emploi étudiant", "Stage",
        "Alternance & apprentissage", "Mission ponctuelle", "Freelance", "Télétravail",
        "Recherche d'employé", "Personnel de maison", "Vente & commercial", "Administration & bureau",
        "Comptabilité & finance", "Informatique & numérique", "Construction & BTP",
        "Hôtellerie & restauration", "Transport & logistique", "Sécurité", "Agriculture & élevage",
        "Autres emplois",
    ],
    "Restauration & Alimentation": [
        "Restaurant", "Snack & fast-food", "Bar & lounge", "Café & salon de thé",
        "Restaurant à vendre", "Restaurant à louer", "Plats maison", "Cuisine africaine",
        "Cuisine internationale", "Traiteur", "Pâtisserie & gâteaux", "Pain & boulangerie",
        "Glaces & desserts", "Boissons & rafraîchissements", "Produits alimentaires", "Épicerie",
        "Aliments en gros", "Livraison de repas", "Cuisinier à domicile", "Serveur & personnel de restaurant",
        "Matériel de restauration", "Autres alimentation",
    ],
    "Agriculture & Élevage": [
        "Produits agricoles", "Fruits & légumes", "Céréales", "Tubercules & plantains",
        "Noix & oléagineux", "Cacao & café", "Miel & produits de ruche", "Semences & plants",
        "Pépinières", "Élevage", "Volaille", "Porcs", "Bovins", "Chèvres & moutons",
        "Poissons & pisciculture", "Aliments pour animaux", "Matériel agricole", "Transformation alimentaire",
        "Produits transformés", "Terrains agricoles", "Autres agriculture",
    ],
    "Matériaux & Construction": [
        "Ciment & liants", "Sable & gravier", "Blocs & briques", "Fer à béton", "Tôles & couverture",
        "Bois & planches", "Carrelage", "Sanitaires", "Peinture", "Plomberie bâtiment",
        "Électricité bâtiment", "Portes & fenêtres", "Aluminium & vitrerie", "Menuiserie",
        "Fer & métallerie", "Outillage", "Machines & équipements BTP", "BTP & chantier",
        "Architecte & dessin bâtiment", "Génie civil & études", "Location matériel de chantier",
        "Autres construction",
    ],
    "Loisirs & Événements": [
        "Événements", "Anniversaires", "Mariages", "Baptêmes & cérémonies", "Conférences & séminaires",
        "Salles & espaces", "Hôtels & espaces événementiels", "Matériel événementiel",
        "DJ & sonorisation", "Éclairage événementiel", "Décoration événementielle",
        "Photographie événementielle", "Vidéo événementielle", "Instruments de musique",
        "Sports & fitness", "Football", "Coach sportif", "Voyage & tourisme",
        "Excursions & visites", "Billetterie événementielle", "Autres loisirs",
    ],
    "Animaux": [
        "Chiens & chats", "Animaux de ferme", "Poissons & aquariophilie", "Oiseaux",
        "Accessoires animaux", "Alimentation animale", "Toilettage", "Pension & garde",
        "Dressage", "Services animaliers", "Autres animaux",
    ],
    "Commerce & Entreprises": [
        "Matériel professionnel", "Fournitures de bureau", "Stock & déstockage", "Grossiste",
        "Détaillant", "Import-export", "Commerce de gros", "Services aux entreprises",
        "Marketing & communication", "Comptabilité & gestion", "Bureaux & domiciliation",
        "Location de matériel", "Franchise & partenariat", "Opportunités commerciales",
        "Entreprise à vendre", "Commerce à vendre", "Commerce à louer", "Autres entreprises",
    ],
    "Éducation & Formation": [
        "Cours particuliers", "Soutien scolaire", "Préparation examens", "Formation informatique",
        "Formation professionnelle", "Langues", "Musique & arts", "Conduite & permis",
        "Formation entreprise", "Autres formation",
    ],
    "Transport & Logistique": [
        "Transport de personnes", "Transport de marchandises", "Livraison", "Coursier",
        "Déménagement", "Location utilitaire", "Logistique", "Transit & expédition",
        "Chauffeur", "Autres transport",
    ],
    "Santé & Bien-être": [
        "Fitness & remise en forme", "Massage & relaxation", "Beauté & soins",
        "Matériel de bien-être", "Produits bien-être", "Services à domicile", "Autres bien-être",
    ],
    "Enfants & Famille": [
        "Puériculture", "Vêtements enfants", "Jouets", "Jeux éducatifs", "École & fournitures",
        "Mobilier enfant", "Anniversaires enfants", "Services de garde", "Autres enfants & famille",
    ],
    "Artisanat & Produits locaux": [
        "Artisanat", "Artisanat du bois", "Artisanat textile", "Poterie & objets décoratifs",
        "Produits locaux", "Produits transformés locaux", "Œuvres & créations", "Autres artisanat",
    ],
    "Autres": [
        "Divers", "Recherche", "À donner", "Perdu & trouvé", "Annonce personnelle", "Autres",
    ],
}


# CityPopulation publishes a city/town table for Cameroon (including places above
# 15,000 inhabitants). We include those places plus several commercially useful
# urban locations. This is intentionally not a claim that these are every hamlet
# or village in the country.
CITIES_BY_REGION = {
    "Adamaoua": [
        "Ngaoundéré", "Meiganga", "Banyo", "Tibati", "Ngaoundal", "Tignère",
        "Djohong", "Mbe", "Belel", "Martap", "Kontcha", "Mayo-Baléo",
    ],
    "Centre": [
        "Yaoundé", "Bafia", "Akonolinga", "Mbalmayo", "Mbandjock", "Nanga-Eboko",
        "Obala", "Soa", "Eséka", "Nkoteng", "Mfou", "Monatélé", "Ngoumou", "Ayos",
        "Makak", "Messondo", "Ntui", "Yoko", "Sa'a", "Bokito", "Makenene",
    ],
    "Est": [
        "Bertoua", "Batouri", "Abong-Mbang", "Garoua-Boulaï", "Bélabo", "Yokadouma",
        "Lomié", "Moloundou", "Doumé", "Dimako", "Kentzou", "Mindourou",
    ],
    "Extrême-Nord": [
        "Maroua", "Kousséri", "Mokolo", "Mora", "Kaélé", "Yagoua", "Bogo", "Guidiguis",
        "Maga", "Blangoua", "Guéré", "Mora", "Kolofata", "Tokombéré", "Koza", "Mayo-Moskota",
    ],
    "Littoral": [
        "Douala", "Edéa", "Nkongsamba", "Mbanga", "Loum", "Manjo", "Melong", "Penja",
        "Njombé", "Yabassi", "Dibombari", "Mouanko", "Dizangué", "Ngambé", "Pouma",
        "Nyanon", "Massock-Songloulou", "Bonaléa", "Bare-Bakem", "Mombo",
    ],
    "Nord": [
        "Garoua", "Guider", "Pitoa", "Lagdo", "Touboro", "Tchéboa", "Figuil", "Mokolo",
        "Bibémi", "Rey-Bouba", "Poli", "Tcholliré", "Dembo", "Ngong",
    ],
    "Nord-Ouest": [
        "Bamenda", "Bafut", "Bali", "Kumbo", "Ndop", "Wum", "Nkambé", "Fundong", "Mbengwi",
        "Ndu", "Batibo", "Santa", "Tubah", "Nkambe", "Jakiri", "Oku",
    ],
    "Ouest": [
        "Bafoussam", "Dschang", "Foumban", "Foumbot", "Bafang", "Bangangté", "Mbouda",
        "Bandjoun", "Kékem", "Magba", "Kouoptamo", "Baham", "Batié", "Bana", "Bangou",
        "Batcham", "Bamendjou", "Mbouda", "Bazou", "Tonga", "Malentouen",
    ],
    "Sud": [
        "Ebolowa", "Kribi", "Sangmélima", "Ambam", "Djoum", "Campo", "Akom II", "Bipindi",
        "Mvangan", "Zoétélé", "Meyomessala", "Mengong", "Oveng", "Lolodorf",
    ],
    "Sud-Ouest": [
        "Buea", "Limbe", "Kumba", "Tiko", "Mutengene", "Muyuka", "Mamfe", "Tombel",
        "Mamfé", "Fontem", "Bangem", "Nguti", "Mundemba", "Ekondo-Titi", "Konye",
        "Akwaya", "Tiko", "Idenau",
    ],
}


# Named neighborhoods/quarters for major urban areas. Smaller towns deliberately
# receive only neutral fallback choices when a reliable detailed source is not
# available in this seed file.
DETAILED_NEIGHBORHOODS = {
    "Douala": [
        "Akwa", "Bonanjo", "Bonapriso", "Bali", "Deido", "New Bell", "Bépanda",
        "Bonamoussadi", "Makepe", "Kotto", "Logbessou", "Ndogbong", "Ndokoti",
        "Logbaba", "Yassa", "Japoma", "Bonabéri", "Mboppi", "Bassa", "Nkongmondo",
        "Bonendale", "Essengue", "Youpwé", "Nyalla", "Ndogpassi", "Cité des Palmiers",
        "Koumassi", "Ngodi", "Nkolmintag", "Congo", "Km 5", "Makea", "Babylone",
        "Ngangue", "Sebenjongo", "Ancien Aéroport", "Nouveau Aéroport", "Grand Moulin",
        "Place de l'UDEAC", "Port", "Base Navale",
    ],
    "Yaoundé": [
        "Centre commercial", "Elig-Essono", "Etoa-Meki", "Nlongkak", "Elig-Edzoa",
        "Bastos", "Manguier", "Tongolo", "Mballa", "Nkolondom", "Etoudi", "Messassi",
        "Olembe", "Emana", "Cité Verte", "Madagascar", "Mokolo", "Grand Messa", "Ekoudou",
        "Tsinga", "Nkom-Kana", "Oliga", "Messa Carrière", "Ntoungou", "Dakar", "Ngoa-Ekelle",
        "Nsimeyong", "Mfoundassi", "Nkondongo", "Odza", "Mimboman", "Ekie Sud", "Melen",
        "Mfandena", "Ngousso", "Simbock", "Mbog-Doum", "Oyom-Abang", "Biyem-Assi",
        "Nkolbisson", "Nsam", "Mvan", "Essos", "Nkol-Eton", "Ahala",
    ],
    "Bafoussam": [
        "Centre-ville", "Kamkop", "Djeleng", "Ndiandam", "Banengo", "Tamja", "Toula Kamga",
        "Kouogouo", "Ndiembou", "Madiba", "Nguinkouo", "Autre quartier",
    ],
    "Bamenda": [
        "Commercial Avenue", "Up Station", "Mankon", "Nkwen", "Mile 2", "Mile 3", "Ntamulung",
        "Ntarikon", "Mulang", "Old Town", "New Layout", "Food Market", "Hospital",
        "Meta Quarter", "Station", "Autre quartier",
    ],
    "Buea": [
        "Molyko", "Great Soppo", "Small Soppo", "Bonduma", "Mile 16", "Mile 17", "Bokwango",
        "Buea Town", "Federal Quarter", "Clerks Quarter", "Government Residential Area",
        "Muea", "Check Point", "Autre quartier",
    ],
    "Limbe": [
        "Down Beach", "Bota", "New Town", "Mile One", "Mile Two", "Mile Four", "Hospital Layout",
        "Church Street", "Federal Quarter", "Clerks Quarter", "Police Barracks", "Limbe Camp GRA",
        "Dockyard", "Town Beach", "Mabeta", "Mawoh", "New Layout", "Custom Quarter",
        "Autre quartier",
    ],
    "Kumba": [
        "Kumba Town", "Fiango", "Mambanda", "Kosala", "Mile One", "Mile Two", "Mile Three",
        "Monte Carlo", "Mile 4", "Barombi Mbo", "Autre quartier",
    ],
    "Kribi": [
        "Centre", "Ngoyé", "New Town", "Mpangou", "Lobé", "Londji", "Bongandoué", "Elabe",
        "Grand Batanga", "Mboamanga", "Petit-Paris", "Zaïre", "Autre quartier",
    ],
    "Ebolowa": ["Centre", "Angalé", "Mekalat", "Ngalan", "New Bell", "Monument", "Autre quartier"],
    "Garoua": [
        "Centre", "Lainde", "Poumpoumré", "Pitoa", "Roumdé-Adjia", "Djamboutou", "Foulbéré",
        "Kolléré", "Marouaré", "Bocklé", "Gare", "Autre quartier",
    ],
    "Maroua": [
        "Pitoaré", "Domayo", "Dougoï", "Hardé", "Comice", "Doursoungo", "Palar", "Kakataré",
        "Pont Vert", "Zokok", "Doualaré", "Ngassa", "Lougguere", "Founangué", "Autre quartier",
    ],
    "Ngaoundéré": [
        "Centre", "Joli Soir", "Bamyanga", "Mbideng", "Marza", "Baladji", "Dang", "Tchabal",
        "Gada Mayo", "Autre quartier",
    ],
    "Nkongsamba": [
        "Eboum 1", "Eboum Dja", "Mouan Dja", "Mouan Mbo", "Nlonko'o", "Edip", "Ekel Ko'o",
        "Ekel Mbeng", "Mbaressoumtou Stade", "Mbaressoumtou Carrière", "Mbaressoumtou Mosquée",
        "Ndogmoa Mbeng", "Edjogmoa", "Ehalmoa", "Bonangoh", "Sosso", "Ekangte Mbeng",
        "Ekol Mbeng", "Mbaressoumtou Aviation", "Mbaressoumtou Village", "Mbaressoumtou Rails", "Poola",
    ],
    "Dschang": ["Centre", "Foréké", "Foto", "Tsinfem", "Site universitaire", "Paidground", "Autre quartier"],
    "Foumban": ["Centre", "Manka", "Njinka", "Mambain", "Autre quartier"],
    "Kousséri": ["Centre", "Administration", "N'Gueli", "Djarma", "Mada", "Autre quartier"],
}


BOOST_PLANS = [
    ("Top 3 jours", 3, 300, "push", "TOP 3 JOURS"),
    ("Top 7 jours", 7, 500, "push", "TOP 7 JOURS"),
    ("Top 14 jours", 14, 1000, "push", "TOP 14 JOURS"),
]

ENTERPRISE_PLANS = [
    ("Entreprise — 7 jours", 7, 15000),
    ("Entreprise — 14 jours", 14, 25000),
    ("Entreprise — 30 jours", 30, 45000),
]


class Command(BaseCommand):
    help = "Initialise le catalogue production de Marché Local pour le Cameroun."

    @staticmethod
    def _city_region_map():
        result = {}
        for region, cities in CITIES_BY_REGION.items():
            for city in cities:
                result[city] = region
        return result

    def _seed_categories(self):
        roots = 0
        children = 0
        for root_position, (root_name, child_names) in enumerate(CATEGORY_TREE.items(), start=1):
            root, _ = Category.objects.update_or_create(
                slug=slugify(root_name),
                defaults={
                    "name": root_name,
                    "position": root_position,
                    "is_active": True,
                    "parent": None,
                },
            )
            roots += 1
            for child_position, child_name in enumerate(child_names, start=1):
                Category.objects.update_or_create(
                    slug=slugify(f"{root_name}-{child_name}"),
                    defaults={
                        "name": child_name,
                        "parent": root,
                        "position": child_position,
                        "is_active": True,
                    },
                )
                children += 1
        return roots, children

    def _seed_cities(self):
        cities = 0
        neighborhoods = 0
        regions = self._city_region_map()

        for city_name, region in sorted(regions.items(), key=lambda item: (item[1], item[0])):
            city, _ = City.objects.update_or_create(
                slug=slugify(city_name),
                defaults={
                    "name": city_name,
                    "region": region,
                    "is_active": True,
                },
            )
            cities += 1

            names = DETAILED_NEIGHBORHOODS.get(
                city_name,
                FALLBACK_NEIGHBORHOODS,
            )

            for neighborhood_name in names:
                name = str(neighborhood_name).strip()
                if not name:
                    continue
                Neighborhood.objects.update_or_create(
                    city=city,
                    slug=slugify(name),
                    defaults={
                        "name": name,
                        "is_active": True,
                    },
                )
                neighborhoods += 1

        return cities, neighborhoods

    def _seed_commercial_plans(self):
        boosts = 0
        enterprises = 0

        for position, (name, days, price, promotion_type, badge) in enumerate(BOOST_PLANS, start=1):
            BoostPlan.objects.update_or_create(
                name=name,
                defaults={
                    "duration_days": days,
                    "price": price,
                    "position": position,
                    "badge": badge,
                    "promotion_type": promotion_type,
                    # V1 remains free. Activate later from admin/settings.
                    "is_active": False,
                },
            )
            boosts += 1

        for position, (name, days, price) in enumerate(ENTERPRISE_PLANS, start=1):
            EnterpriseAdPlan.objects.update_or_create(
                name=name,
                defaults={
                    "duration_days": days,
                    "price": price,
                    "position": position,
                    "is_active": False,
                },
            )
            enterprises += 1

        return boosts, enterprises

    def _configure_platform(self):
        config = PlatformSettings.load()

        # These fields exist in the current V1 project.
        config.listing_days = min(30, max(1, int(getattr(config, "listing_days", 30) or 30)))
        config.renewal_notice_days = min(30, max(1, int(getattr(config, "renewal_notice_days", 3) or 3)))

        # Be defensive if a later project revision contains these fields.
        optional = {
            "monetization_enabled": False,
            "is_monetised": False,
            "enterprise_enabled": False,
            "listing_max_days": 30,
            "max_listing_days": 30,
            "default_listing_days": 30,
        }
        field_names = {f.name for f in config._meta.get_fields() if hasattr(f, "name")}
        for name, value in optional.items():
            if name in field_names:
                setattr(config, name, value)

        config.save()
        return config

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Mise à jour du catalogue Marché Local…"))

        root_count, child_count = self._seed_categories()
        city_count, neighborhood_count = self._seed_cities()
        boost_count, enterprise_count = self._seed_commercial_plans()
        config = self._configure_platform()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✓ Catalogue Marché Local prêt."))
        self.stdout.write(f"  Catégories principales : {root_count}")
        self.stdout.write(f"  Sous-catégories        : {child_count}")
        self.stdout.write(f"  Villes/localités       : {city_count}")
        self.stdout.write(f"  Quartiers              : {neighborhood_count}")
        self.stdout.write(f"  Plans Boost            : {boost_count}")
        self.stdout.write(f"  Plans Entreprise       : {enterprise_count}")
        self.stdout.write(f"  Durée par défaut       : {config.listing_days} jour(s)")
        self.stdout.write(f"  Alerte renouvellement  : {config.renewal_notice_days} jour(s)")
        self.stdout.write("  Monétisation           : désactivée")
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE(
            "Aucune donnée existante n'est supprimée; les catégories, villes et "
            "quartiers déjà utilisés par des annonces restent protégés."
        ))
        self.stdout.write(self.style.NOTICE(
            "Les petits centres reçoivent seulement des choix génériques de localisation "
            "tant qu'une liste locale de quartiers n'est pas confirmée."
        ))
