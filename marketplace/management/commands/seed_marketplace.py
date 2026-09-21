from django.core.management.base import BaseCommand
from django.utils.text import slugify

from marketplace.models import BoostPlan, Category, City, EnterpriseAdPlan, Neighborhood, PlatformSettings


CATEGORY_TREE = {
    "Immobilier": [
        "Vente maison & appartement",
        "Location maison & appartement",
        "Studios & chambres",
        "Terrains",
        "Bureaux & locaux",
        "Boutiques & magasins",
        "Colocation",
        "Immobilier commercial",
    ],
    "Véhicules": [
        "Voitures",
        "Motos & scooters",
        "Camions & utilitaires",
        "Pièces & accessoires",
        "Pneus & batteries",
        "Location de véhicules",
    ],
    "Téléphones & Informatique": [
        "Téléphones & smartphones",
        "Ordinateurs & laptops",
        "Tablettes",
        "Télévisions & audio",
        "Accessoires téléphone",
        "Composants & réseaux",
    ],
    "Maison & Électroménager": [
        "Meubles",
        "Électroménager",
        "Cuisine",
        "Matériel de maison",
        "Décoration",
        "Jardin & extérieur",
    ],
    "Mode & Beauté": [
        "Vêtements",
        "Chaussures",
        "Sacs & accessoires",
        "Cosmétiques",
        "Coiffure & barber",
        "Mode homme",
        "Mode femme",
        "Enfants",
    ],
    "Services": [
        "Plomberie",
        "Électricité",
        "Peinture & finition",
        "Ménage & nettoyage",
        "Réparation téléphone",
        "Informatique & réseaux",
        "Développement web & logiciel",
        "Graphisme & communication",
        "Photographie & vidéo",
        "Couture & retouche",
        "Coiffure & esthétique",
        "Livraison & courses",
        "Déménagement",
        "Transport",
        "Sécurité",
        "Cours particuliers",
        "Traduction & rédaction",
        "Maintenance & dépannage",
        "DJ & animation",
        "Cuisine & service traiteur",
        "Serveur & service événementiel",
        "Services Mobile Money",
        "Conseil & accompagnement",
        "Événementiel",
        "Autres services",
    ],
    "Emploi & Missions": [
        "Emploi",
        "Stage",
        "Mission ponctuelle",
        "Freelance",
        "Apprentissage",
        "Recherche d'employé",
    ],
    "Restauration & Alimentation": [
        "Restaurant",
        "Bar & lounge",
        "Restaurant à vendre",
        "Plats maison",
        "Traiteur",
        "Pâtisserie & gâteaux",
        "Snacks & fast-food",
        "Boissons & rafraîchissements",
        "Produits alimentaires",
        "Livraison de repas",
    ],
    "Agriculture & Élevage": [
        "Produits agricoles",
        "Semences & plants",
        "Élevage",
        "Matériel agricole",
        "Bétail & volaille",
        "Transformation alimentaire",
    ],
    "Matériaux & Construction": [
        "Matériaux de construction",
        "Carrelage & sanitaire",
        "Bois & menuiserie",
        "Aluminium & vitrerie",
        "Fer & métallerie",
        "BTP & chantier",
    ],
    "Loisirs & Événements": [
        "Événements",
        "Salles & espaces",
        "Matériel événementiel",
        "DJ & sonorisation",
        "Décoration événementielle",
        "Instruments de musique",
        "Sports & fitness",
        "Voyage & tourisme",
    ],
    "Animaux": [
        "Chiens & chats",
        "Animaux de ferme",
        "Accessoires animaux",
        "Services animaliers",
    ],
    "Commerce & Entreprises": [
        "Matériel professionnel",
        "Fournitures de bureau",
        "Stock & déstockage",
        "Services aux entreprises",
        "Opportunités commerciales",
    ],
    "Enfants & Famille": [
        "Puériculture",
        "Jouets",
        "École & fournitures",
        "Mobilier enfant",
    ],
    "Autres": [
        "À donner",
        "Recherche",
        "Divers",
    ],
}


CITY_DATA = {
    "Douala": {
        "region": "Littoral",
        "neighborhoods": [
            "Akwa", "Bonapriso", "Bonamoussadi", "Makepe", "Deido", "Bépanda",
            "Logbessou", "Bonabéri", "New Bell", "Kotto", "Bali", "Cité des Palmiers",
            "Yassa", "Japoma", "PK 8", "PK 12", "Ndogbong", "Ndokoti",
        ],
    },
    "Yaoundé": {
        "region": "Centre",
        "neighborhoods": [
            "Bastos", "Mvan", "Odza", "Essos", "Mokolo", "Nsam", "Etoudi",
            "Tsinga", "Messassi", "Mfandena", "Biyem-Assi", "Nkolbisson", "Emana",
        ],
    },
    "Bafoussam": {"region": "Ouest", "neighborhoods": ["Centre", "Djeleng", "Tamdja", "Banengo"]},
    "Bamenda": {"region": "Nord-Ouest", "neighborhoods": ["Commercial Avenue", "Nkwen", "Mankon", "Ntamulung"]},
    "Buea": {"region": "Sud-Ouest", "neighborhoods": ["Molyko", "Great Soppo", "Bonduma", "Federal Quarter"]},
    "Limbe": {"region": "Sud-Ouest", "neighborhoods": ["Down Beach", "Bota", "New Town", "Mile 4"]},
    "Kribi": {"region": "Sud", "neighborhoods": ["Centre", "Ngoyé", "Londji", "Grand Batanga"]},
    "Garoua": {"region": "Nord", "neighborhoods": ["Centre", "Pitoa", "Poumpoumré", "Lainde"]},
    "Maroua": {"region": "Extrême-Nord", "neighborhoods": ["Pitoaré", "Dougoi", "Domayo", "Comice"]},
    "Ngaoundéré": {"region": "Adamaoua", "neighborhoods": ["Centre", "Mbideng", "Marza", "Baladji"]},
    "Bertoua": {"region": "Est", "neighborhoods": ["Centre", "Nkolbikon", "Kpokolota", "Enia"]},
    "Ebolowa": {"region": "Sud", "neighborhoods": ["Centre", "Angalé", "Mekalat", "Ngalan"]},
    "Kumba": {"region": "Sud-Ouest", "neighborhoods": ["Kumba Town", "Fiango", "Mambanda", "Kosala"]},
    "Nkongsamba": {"region": "Littoral", "neighborhoods": ["Centre", "Pool", "Melong", "Quartier Haoussa"]},
    "Edéa": {"region": "Littoral", "neighborhoods": ["Centre", "Nkolbong", "Sachs", "Ekité"]},
    "Dschang": {"region": "Ouest", "neighborhoods": ["Centre", "Foréké", "Tsinfem", "Foto"]},
}


BOOST_PLANS = [
    ("Top 3 jours", 3, 300, "push", "TOP 3 JOURS"),
    ("Top 7 jours", 7, 500, "push", "TOP 7 JOURS"),
    ("Top 14 jours", 14, 1000, "push", "TOP 14 JOURS"),
]


class Command(BaseCommand):
    help = "Initialise les catégories, villes, quartiers, plans commerciaux et la configuration."

    def handle(self, *args, **options):
        for root_position, (root_name, children) in enumerate(CATEGORY_TREE.items(), start=1):
            root, _ = Category.objects.update_or_create(
                slug=slugify(root_name),
                defaults={"name": root_name, "position": root_position, "is_active": True, "parent": None},
            )
            for child_position, child_name in enumerate(children, start=1):
                Category.objects.update_or_create(
                    slug=slugify(f"{root_name}-{child_name}"),
                    defaults={
                        "name": child_name,
                        "parent": root,
                        "position": child_position,
                        "is_active": True,
                    },
                )

        for city_name, data in CITY_DATA.items():
            city, _ = City.objects.update_or_create(
                slug=slugify(city_name),
                defaults={"name": city_name, "region": data["region"], "is_active": True},
            )
            for position, neighborhood in enumerate(data["neighborhoods"], start=1):
                Neighborhood.objects.update_or_create(
                    city=city,
                    slug=slugify(neighborhood),
                    defaults={"name": neighborhood, "is_active": True},
                )

        for position, (name, days, price, promotion_type, badge) in enumerate(BOOST_PLANS, start=1):
            BoostPlan.objects.update_or_create(
                name=name,
                defaults={
                    "duration_days": days,
                    "price": price,
                    "position": position,
                    "badge": badge,
                    "promotion_type": promotion_type,
                    "is_active": False,
                },
            )

        EnterpriseAdPlan.objects.update_or_create(
            name="Entreprise — 7 jours",
            defaults={"duration_days": 7, "price": 15000, "position": 1, "is_active": False},
        )

        config = PlatformSettings.load()
        config.listing_days = min(30, max(1, config.listing_days))
        config.renewal_notice_days = min(30, max(1, config.renewal_notice_days))
        config.save()

        self.stdout.write(self.style.SUCCESS("Marché Local initialisé avec un catalogue adapté au Cameroun. La monétisation reste désactivée."))
