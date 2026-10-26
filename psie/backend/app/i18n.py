"""Textes de l'interface en français et en arabe.

Les traductions arabes sont une première version à faire relire par un locuteur
avant mise en ligne. Une clé absente retombe sur le français, puis sur la clé elle-même.
"""

from .public_texts import PUBLIC_TEXTS

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
    "nav_dues": {"fr": "Cotisations", "ar": "الاشتراكات"},
    "total_due": {"fr": "Total dû", "ar": "المجموع المستحق"},
    "total_paid": {"fr": "Total encaissé", "ar": "المجموع المحصل"},
    "recovery_rate": {"fr": "Taux de recouvrement", "ar": "نسبة التحصيل"},
    "late_count": {"fr": "En retard", "ar": "متأخرة"},
    "up_to_date": {"fr": "À jour", "ar": "مسددة"},
    "remaining": {"fr": "Reste à encaisser", "ar": "المتبقي للتحصيل"},
    "annual_amount": {"fr": "Montant de la cotisation annuelle", "ar": "مبلغ الاشتراك السنوي"},
    "deadline": {"fr": "Date limite", "ar": "الأجل"},
    "no_amount": {"fr": "Aucun montant défini pour cette année.", "ar": "لم يحدد أي مبلغ لهذه السنة."},
    "amount": {"fr": "Montant", "ar": "المبلغ"},
    "decision_ref": {"fr": "Référence de la décision", "ar": "مرجع القرار"},
    "missing_dues": {"fr": "cotisation(s) à créer", "ar": "اشتراك(ات) للإنشاء"},
    "open_year": {"fr": "Créer les cotisations de l'année", "ar": "إنشاء اشتراكات السنة"},
    "situation": {"fr": "Situation par faîtière", "ar": "الوضعية حسب المنظمة"},
    "export_csv": {"fr": "Exporter (CSV)", "ar": "تصدير (CSV)"},
    "due": {"fr": "Dû", "ar": "المستحق"},
    "paid": {"fr": "Payé", "ar": "المدفوع"},
    "balance": {"fr": "Solde", "ar": "الرصيد"},
    "adhesion_fee": {"fr": "Droit d'adhésion", "ar": "رسم الانخراط"},
    "payments": {"fr": "Paiements", "ar": "المدفوعات"},
    "receipt": {"fr": "Reçu", "ar": "الإيصال"},
    "mode": {"fr": "Mode", "ar": "الطريقة"},
    "reference": {"fr": "Référence", "ar": "المرجع"},
    "cancelled": {"fr": "Annulé", "ar": "ملغى"},
    "cancel": {"fr": "Annuler", "ar": "إلغاء"},
    "cancel_reason": {"fr": "Motif de l'annulation", "ar": "سبب الإلغاء"},
    "record_payment": {"fr": "Enregistrer un paiement", "ar": "تسجيل دفعة"},
    "attestation": {"fr": "Attestation", "ar": "شهادة"},
    "verification": {"fr": "Vérification", "ar": "التحقق"},
    "receipt_valid": {"fr": "Reçu authentique", "ar": "إيصال صحيح"},
    "receipt_cancelled": {"fr": "Ce reçu a été annulé.", "ar": "تم إلغاء هذا الإيصال."},
    "attestation_valid": {"fr": "Cotisation à jour", "ar": "الاشتراك مسدد"},
    "attestation_not_up_to_date": {"fr": "Cette faîtière n'est pas (ou plus) à jour.", "ar": "هذه المنظمة غير مسددة."},
    "year": {"fr": "Année", "ar": "السنة"},
    "verify_title": {"fr": "Vérification du code", "ar": "التحقق من الرمز"},
    "verify_help": {"fr": "Un code à 6 chiffres vient d'être envoyé à votre adresse e-mail.", "ar": "تم إرسال رمز من 6 أرقام إلى بريدك الإلكتروني."},
    "code": {"fr": "Code", "ar": "الرمز"},
    "verify": {"fr": "Valider", "ar": "تأكيد"},
    "code_error": {"fr": "Code incorrect.", "ar": "الرمز غير صحيح."},
    "login_2fa_unavailable": {
        "fr": "Impossible d'envoyer le code de connexion (e-mail non configuré). Contactez l'administrateur.",
        "ar": "تعذر إرسال رمز الدخول (البريد غير مهيأ). اتصل بالمسؤول.",
    },
    "nav_calls": {"fr": "Appels exceptionnels", "ar": "النداءات الاستثنائية"},
    "call_title": {"fr": "Intitulé", "ar": "العنوان"},
    "call_reason": {"fr": "Motif", "ar": "السبب"},
    "common_amount": {"fr": "Montant commun (FCFA)", "ar": "المبلغ المشترك (فرنك)"},
    "own_amount": {"fr": "Montant propre (facultatif)", "ar": "مبلغ خاص (اختياري)"},
    "include": {"fr": "Inclure", "ar": "إدراج"},
    "new_call": {"fr": "Nouvel appel de fonds", "ar": "نداء جديد"},
    "call_help": {
        "fr": "Cochez les faîtières concernées. Le montant propre l'emporte sur le montant commun.",
        "ar": "حدد المنظمات المعنية. المبلغ الخاص يسبق المبلغ المشترك.",
    },
    "solved": {"fr": "Soldé", "ar": "مسدد"},
    "in_progress": {"fr": "En cours", "ar": "جار"},
    "exempt": {"fr": "Exonérer", "ar": "إعفاء"},
    "restore": {"fr": "Rétablir", "ar": "استرجاع"},
    "postpone": {"fr": "Reporter", "ar": "تأجيل"},
    "new_deadline": {"fr": "Nouvelle date limite", "ar": "أجل جديد"},
    "fix_amount": {"fr": "Corriger le montant", "ar": "تصحيح المبلغ"},
    "reason": {"fr": "Motif", "ar": "السبب"},
    "exempted_reason": {"fr": "Exonérée", "ar": "معفاة"},
    "st_exonere": {"fr": "Exonéré", "ar": "معفى"},
    "actions": {"fr": "Actions", "ar": "إجراءات"},
    "st_paye": {"fr": "À jour", "ar": "مسدد"},
    "st_partiel": {"fr": "Partiel", "ar": "جزئي"},
    "st_en_retard": {"fr": "En retard", "ar": "متأخر"},
    "st_impaye": {"fr": "Impayé", "ar": "غير مسدد"},
}


TEXTS.update(PUBLIC_TEXTS)


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
