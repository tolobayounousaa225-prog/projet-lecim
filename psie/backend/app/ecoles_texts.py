"""Textes (FR/AR) du bloc « écoles, statistiques, annonces et demandes » des faîtières.
Les traductions arabes sont à faire relire par un locuteur avant mise en ligne."""


def _t(fr: str, ar: str) -> dict[str, str]:
    return {"fr": fr, "ar": ar}


ECOLES_TEXTS = {
    "nav_stats": _t("Statistiques", "الإحصائيات"),
    "nav_announcements": _t("Annonces", "الإعلانات"),
    "nav_requests": _t("Demandes", "الطلبات"),
    "nav_group_federations": _t("Suivi des faîtières", "متابعة المنظمات"),
    "e_year": _t("Année", "السنة"), "e_level": _t("Niveau", "المستوى"), "e_locality": _t("Localité", "المنطقة"),
    "e_director": _t("Directeur / directrice", "المدير"), "e_list": _t("Liste des écoles affiliées", "قائمة المدارس المنتسبة"),
    "e_export": _t("Exporter (Excel/CSV)", "تصدير (Excel/CSV)"),
    "e_import": _t("Importer une liste d'écoles", "استيراد قائمة مدارس"),
    "e_import_help": _t("Fichier CSV (enregistré depuis Excel) : nom ; localité ; DRENA ; téléphone ; niveau ; directeur. Les écoles déjà enregistrées ne sont pas dupliquées.",
                        "ملف CSV (محفوظ من Excel): الاسم ؛ المنطقة ؛ DRENA ؛ الهاتف ؛ المستوى ؛ المدير. لا تتكرر المدارس المسجلة."),
    "e_import_btn": _t("Importer", "استيراد"),
    "e_schools_count": _t("Écoles affiliées", "المدارس المنتسبة"), "e_pupils": _t("Élèves", "التلاميذ"),
    "e_staff_total": _t("Personnel total", "مجموع الموظفين"), "e_francophone": _t("Francophones", "الناطقون بالفرنسية"),
    "e_arabisant": _t("Arabisants", "الناطقون بالعربية"), "e_admin": _t("Administratifs", "الإداريون"),
    "e_teachers": _t("Enseignants", "المدرّسون"),
    "e_census": _t("Recensement du personnel et des élèves", "إحصاء الموظفين والتلاميذ"),
    "e_census_help": _t("Le total du personnel est calculé automatiquement. Enregistrer une année déjà saisie la remplace.",
                        "يُحسب مجموع الموظفين تلقائيا. حفظ سنة مسجلة سابقا يستبدلها."),
    "e_admin_fr": _t("Administratifs francophones", "إداريون ناطقون بالفرنسية"),
    "e_admin_ar": _t("Administratifs arabisants", "إداريون ناطقون بالعربية"),
    "e_teach_fr": _t("Enseignants francophones", "مدرّسون ناطقون بالفرنسية"),
    "e_teach_ar": _t("Enseignants arabisants", "مدرّسون ناطقون بالعربية"),
    "e_exams": _t("Résultats d'examens", "نتائج الامتحانات"), "e_exam": _t("Examen", "الامتحان"),
    "e_candidates": _t("Candidats", "المترشحون"), "e_passed": _t("Admis", "الناجحون"), "e_rate": _t("Taux", "النسبة"),
    "e_pass_rate": _t("Taux de réussite", "نسبة النجاح"),
    "e_reports": _t("Bilans annuels", "الحصيلة السنوية"), "e_summary": _t("Résumé de l'année", "ملخص السنة"),
    "e_difficulties": _t("Difficultés rencontrées", "الصعوبات"), "e_outlook": _t("Perspectives", "الآفاق"),
    "e_opinion": _t("Avis de la PSIE", "رأي المنصة"), "e_propose_report": _t("Proposer un bilan", "اقتراح حصيلة"),
    "e_save_draft": _t("Enregistrer en brouillon", "حفظ كمسودة"), "e_submit": _t("Proposer à la PSIE", "اقتراح على المنصة"),
    "e_validate": _t("Valider", "اعتماد"), "e_to_fix": _t("Demander une correction", "طلب تصحيح"),
    "e_by_federation": _t("Chiffres par faîtière", "الأرقام حسب المنظمة"), "e_total": _t("Total", "المجموع"),
    "e_reports_valid": _t("Bilans validés", "الحصائل المعتمدة"), "e_up_to_date": _t("À jour", "مسددة"),
    "e_not_up_to_date": _t("En retard", "متأخرة"), "e_evolution": _t("Évolution par année", "التطور حسب السنة"),
    "e_average": _t("Moyenne des faîtières", "متوسط المنظمات"), "e_staff_breakdown": _t("Répartition du personnel", "توزيع الموظفين"),
    "e_census_progress": _t("Écoles recensées", "المدارس المحصاة"),
    "e_dashboard": _t("Tableau de bord de la faîtière", "لوحة المنظمة"), "e_dossier": _t("Dossier à compléter", "الملف المطلوب استكماله"),
    "e_next_events": _t("Prochaines échéances", "المواعيد القادمة"),
    "step_pieces": _t("Pièces justificatives déposées", "إيداع الوثائق"), "step_delegates": _t("Délégués régionaux renseignés", "تسجيل المندوبين الجهويين"),
    "step_schools": _t("Écoles affiliées enregistrées", "تسجيل المدارس المنتسبة"), "step_census": _t("Recensement de toutes les écoles", "إحصاء جميع المدارس"),
    "step_reports": _t("Bilans proposés pour toutes les écoles", "اقتراح حصائل جميع المدارس"), "step_dues": _t("Cotisation à jour", "الاشتراك مسدد"),
    "r_all": _t("Toutes les faîtières", "جميع المنظمات"), "r_new_announcement": _t("Nouvelle annonce", "إعلان جديد"),
    "r_title": _t("Titre", "العنوان"), "r_message": _t("Message", "الرسالة"), "r_target": _t("Destinataire", "المرسل إليه"),
    "r_publish": _t("Publier", "نشر"), "r_new_request": _t("Nouvelle demande à la PSIE", "طلب جديد إلى المنصة"),
    "r_type": _t("Type de demande", "نوع الطلب"), "r_subject": _t("Objet", "الموضوع"), "r_send": _t("Envoyer", "إرسال"),
    "r_answer": _t("Réponse de la PSIE", "جواب المنصة"),
    "dash_sec_ecoles": _t("Écoles et suivi des faîtières", "المدارس ومتابعة المنظمات"),
}

ECOLES_LABELS = {
    "niveau": {
        "prescolaire": _t("Préscolaire", "التحضيري"), "primaire": _t("Primaire", "الابتدائي"), "secondaire": _t("Secondaire", "الثانوي"),
        "mixte": _t("Plusieurs niveaux", "مستويات متعددة"), "superieur": _t("Supérieur / formation", "عالٍ / تكوين"),
    },
    "examen": {
        "cepe": _t("CEPE", "شهادة الدراسة الابتدائية"), "bepc": _t("BEPC", "شهادة التعليم المتوسط"), "bac": _t("Baccalauréat", "البكالوريا"),
        "arabe_primaire": _t("Examen d'arabe (primaire)", "امتحان العربية (ابتدائي)"),
        "arabe_secondaire": _t("Examen d'arabe (secondaire)", "امتحان العربية (ثانوي)"),
    },
    "bilan": {
        "brouillon": _t("Brouillon", "مسودة"), "soumis": _t("Proposé à la PSIE", "مقترح على المنصة"),
        "a_corriger": _t("À corriger", "يحتاج تصحيحا"), "valide": _t("Validé", "معتمد"),
    },
    "demande_type": {
        "attestation": _t("Attestation", "شهادة"), "rendez_vous": _t("Rendez-vous", "موعد"),
        "soutien": _t("Soutien / accompagnement", "دعم ومرافقة"), "information": _t("Demande d'information", "طلب معلومات"),
        "autre": _t("Autre", "أخرى"),
    },
    "demande_statut": {"ouverte": _t("Ouverte", "مفتوح"), "en_cours": _t("En cours", "قيد المعالجة"), "traitee": _t("Traitée", "تمت المعالجة")},
}
