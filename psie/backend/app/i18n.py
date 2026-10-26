"""Textes de l'interface en français et en arabe.

Les traductions arabes sont une première version à faire relire par un locuteur
avant mise en ligne. Une clé absente retombe sur le français, puis sur la clé elle-même.
"""

SUPPORTED_LANGS = ("fr", "ar")
DEFAULT_LANG = "fr"

TEXTS: dict[str, dict[str, str]] = {
    "app_name": {"fr": "PSIE", "ar": "PSIE"},
    "app_full_name": {
        "fr": "Plateforme des Structures Islamiques d'Éducation",
        "ar": "منصة الهياكل الإسلامية للتعليم",
    },
    "nav_dashboard": {"fr": "Tableau de bord", "ar": "لوحة القيادة"},
    "nav_members": {"fr": "Membres", "ar": "الأعضاء"},
    "nav_mandates": {"fr": "Mandats", "ar": "الانتدابات"},
    "nav_users": {"fr": "Comptes", "ar": "الحسابات"},
    "nav_audit": {"fr": "Journal d'audit", "ar": "سجل المراجعة"},
    "nav_my_org": {"fr": "Ma faîtière", "ar": "منظمتي"},
    "logout": {"fr": "Déconnexion", "ar": "تسجيل الخروج"},
    "login_title": {"fr": "Connexion", "ar": "تسجيل الدخول"},
    "email": {"fr": "Adresse e-mail", "ar": "البريد الإلكتروني"},
    "password": {"fr": "Mot de passe", "ar": "كلمة المرور"},
    "sign_in": {"fr": "Se connecter", "ar": "دخول"},
    "login_error": {"fr": "Identifiants incorrects.", "ar": "بيانات الدخول غير صحيحة."},
    "login_locked": {
        "fr": "Compte verrouillé temporairement. Réessayez dans quelques minutes.",
        "ar": "الحساب مقفل مؤقتا. أعد المحاولة بعد دقائق.",
    },
    "members_active": {"fr": "Membres actifs", "ar": "الأعضاء النشطون"},
    "members_total": {"fr": "Membres au total", "ar": "مجموع الأعضاء"},
    "mandates_expiring": {"fr": "Mandats arrivant à échéance (90 jours)", "ar": "انتدابات تنتهي خلال 90 يوما"},
    "mandates_expired": {"fr": "Mandats expirés", "ar": "انتدابات منتهية"},
    "none": {"fr": "Aucun", "ar": "لا يوجد"},
    "name": {"fr": "Nom", "ar": "الاسم"},
    "acronym": {"fr": "Sigle", "ar": "الاختصار"},
    "category": {"fr": "Catégorie", "ar": "الفئة"},
    "status": {"fr": "Statut", "ar": "الحالة"},
    "add": {"fr": "Ajouter", "ar": "إضافة"},
    "save": {"fr": "Enregistrer", "ar": "حفظ"},
    "edit": {"fr": "Modifier", "ar": "تعديل"},
    "delete": {"fr": "Supprimer", "ar": "حذف"},
    "back": {"fr": "Retour", "ar": "رجوع"},
    "new_member": {"fr": "Nouveau membre", "ar": "عضو جديد"},
    "full_name": {"fr": "Nom complet", "ar": "الاسم الكامل"},
    "role": {"fr": "Rôle", "ar": "الدور"},
    "organ": {"fr": "Organe", "ar": "الهيئة"},
    "function": {"fr": "Fonction", "ar": "الوظيفة"},
    "start_date": {"fr": "Début", "ar": "البداية"},
    "end_date": {"fr": "Fin", "ar": "النهاية"},
    "phone": {"fr": "Téléphone", "ar": "الهاتف"},
    "seat": {"fr": "Siège", "ar": "المقر"},
    "created_on": {"fr": "Date de création", "ar": "تاريخ التأسيس"},
    "joined_on": {"fr": "Date d'adhésion", "ar": "تاريخ الانضمام"},
    "legal_status": {"fr": "Statut juridique", "ar": "الوضع القانوني"},
    "notes": {"fr": "Notes", "ar": "ملاحظات"},
    "mandates_of": {"fr": "Représentants et mandats", "ar": "الممثلون والانتدابات"},
    "organisation": {"fr": "Faîtière", "ar": "المنظمة"},
    "none_organisation": {"fr": "— Aucune (organe national) —", "ar": "— لا شيء (هيئة وطنية) —"},
    "active": {"fr": "Actif", "ar": "نشط"},
    "disabled": {"fr": "Désactivé", "ar": "معطل"},
    "toggle": {"fr": "Activer / désactiver", "ar": "تفعيل / تعطيل"},
    "date": {"fr": "Date", "ar": "التاريخ"},
    "user": {"fr": "Utilisateur", "ar": "المستخدم"},
    "action": {"fr": "Action", "ar": "الإجراء"},
    "detail": {"fr": "Détail", "ar": "التفاصيل"},
    "language": {"fr": "Langue", "ar": "اللغة"},
}


def translate(key: str, lang: str) -> str:
    entry = TEXTS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(DEFAULT_LANG) or key


def normalize_lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


# Libellés des valeurs de données (catégories, statuts, organes, rôles)
LABELS: dict[str, dict[str, dict[str, str]]] = {
    "categorie": {
        "fondateur": {"fr": "Membre fondateur", "ar": "عضو مؤسس"},
        "ordinaire": {"fr": "Membre ordinaire", "ar": "عضو عادي"},
        "honneur": {"fr": "Membre d'honneur", "ar": "عضو شرف"},
    },
    "statut": {
        "actif": {"fr": "Actif", "ar": "نشط"},
        "suspendu": {"fr": "Suspendu", "ar": "موقوف"},
        "radie": {"fr": "Radié", "ar": "مشطوب"},
        "demissionnaire": {"fr": "Démissionnaire", "ar": "مستقيل"},
    },
    "organe": {
        "AG": {"fr": "Assemblée Générale (délégué)", "ar": "الجمعية العامة (مندوب)"},
        "CA": {"fr": "Conseil d'Administration", "ar": "مجلس الإدارة"},
        "DEN": {"fr": "Direction Exécutive Nationale", "ar": "المديرية التنفيذية الوطنية"},
        "CC": {"fr": "Commissariat aux Comptes", "ar": "مفوضية الحسابات"},
        "CNECI": {"fr": "Commission des Examens et Concours Islamiques", "ar": "اللجنة الوطنية للامتحانات والمسابقات الإسلامية"},
        "CNVSP": {"fr": "Commission de Validation et Suivi des Programmes", "ar": "اللجنة الوطنية لاعتماد الكتب ومتابعة البرامج"},
    },
    "role": {
        "admin": {"fr": "Administrateur de la plate-forme", "ar": "مسؤول المنصة"},
        "den": {"fr": "Directeur Exécutif National", "ar": "المدير التنفيذي الوطني"},
        "finances": {"fr": "Secrétaire chargé des finances (ou adjoint)", "ar": "الأمين المكلف بالشؤون المالية (أو نائبه)"},
        "secretaire": {"fr": "Secrétaire de la DEN", "ar": "أمين المديرية التنفيذية"},
        "administrateur_ca": {"fr": "Administrateur du CA", "ar": "عضو مجلس الإدارة"},
        "commissaire": {"fr": "Commissaire aux comptes", "ar": "مفوض الحسابات"},
        "faitiere": {"fr": "Représentant de faîtière", "ar": "ممثل منظمة"},
    },
}


def label(kind: str, key: str, lang: str) -> str:
    entry = LABELS.get(kind, {}).get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(DEFAULT_LANG) or key
