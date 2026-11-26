"""Textes (FR/AR) du module 4 : documents, courrier, conventions, registres. Arabe à faire relire avant mise en ligne."""


def _t(fr: str, ar: str) -> dict[str, str]:
    return {"fr": fr, "ar": ar}


DOCUMENTS_TEXTS = {
    "nav_group_docs": _t("Documents et registres", "الوثائق والسجلات"),
    "nav_documents": _t("Documents", "الوثائق"), "nav_mail": _t("Courrier", "المراسلات"),
    "nav_agreements": _t("Conventions", "الاتفاقيات"), "nav_registers": _t("Registres légaux", "السجلات القانونية"),
    "d_title": _t("Titre", "العنوان"), "d_category": _t("Catégorie", "الفئة"), "d_description": _t("Description", "الوصف"),
    "d_file": _t("Fichier (PDF ou image)", "الملف (PDF أو صورة)"), "d_restricted": _t("Restreint (réservé à ceux qui modifient)", "مقيّد (لمن يملك حق التعديل فقط)"),
    "d_search": _t("Rechercher", "بحث"), "d_all": _t("Toutes", "الكل"), "d_download": _t("Télécharger", "تحميل"),
    "d_added": _t("Ajouté le", "أضيف في"), "d_add_doc": _t("Déposer un document", "إيداع وثيقة"),
    "m_number": _t("N°", "الرقم"), "m_direction": _t("Sens", "الاتجاه"), "m_date": _t("Date", "التاريخ"),
    "m_correspondent": _t("Correspondant", "المراسل"), "m_subject": _t("Objet", "الموضوع"), "m_reference": _t("Référence du courrier", "مرجع المراسلة"),
    "m_owner": _t("Responsable", "المسؤول"), "m_deadline": _t("Échéance", "الأجل"), "m_note": _t("Note", "ملاحظة"),
    "m_late": _t("courrier(s) en retard", "مراسلة متأخرة"), "m_new": _t("Enregistrer un courrier", "تسجيل مراسلة"),
    "m_reply_to": _t("En réponse à", "ردا على"), "m_replies": _t("Réponses", "الردود"), "m_follow": _t("Suivi", "المتابعة"),
    "m_overdue": _t("En retard", "متأخر"),
    "c_partner": _t("Partenaire", "الشريك"), "c_amount": _t("Montant (FCFA)", "المبلغ (فرنك)"), "c_start": _t("Début", "البداية"),
    "c_end": _t("Fin", "النهاية"), "c_circuit": _t("Circuit d'approbation", "مسار الاعتماد"), "c_history": _t("Historique", "السجل"),
    "c_submit": _t("Soumettre au CA", "إحالة إلى المجلس"), "c_favourable": _t("Avis favorable", "رأي إيجابي"),
    "c_unfavourable": _t("Avis défavorable", "رأي سلبي"), "c_sign": _t("Signer (DEN)", "التوقيع (المدير التنفيذي)"),
    "c_comment": _t("Commentaire", "تعليق"), "c_new": _t("Nouvelle convention", "اتفاقية جديدة"),
    "c_help": _t("Le DEN prépare, le Conseil d'Administration donne son avis, puis le DEN signe.",
                 "يعدّ المدير التنفيذي الاتفاقية، ثم يبدي مجلس الإدارة رأيه، ثم يوقّع المدير."),
    "r_help": _t("Les entrées d'un registre ne se modifient ni ne se suppriment : chacune est chaînée à la précédente par une empreinte.",
                 "لا تُعدَّل مدخلات السجل ولا تُحذف: كل مدخل مرتبط بسابقه ببصمة."),
    "r_intact": _t("Intégrité vérifiée : aucune entrée n'a été altérée.", "تم التحقق من السلامة: لم يُعدَّل أي مدخل."),
    "r_broken": _t("ATTENTION : la chaîne est rompue à partir de l'entrée n°", "تنبيه: السلسلة منقطعة ابتداء من المدخل رقم"),
    "r_entries": _t("entrée(s)", "مدخل"), "r_new": _t("Nouvelle entrée", "مدخل جديد"), "r_act_date": _t("Date de l'acte", "تاريخ العقد"),
    "r_summary": _t("Résumé / contenu de la délibération", "ملخص المداولة"), "r_document": _t("Document lié", "وثيقة مرتبطة"),
    "r_assembly": _t("Assemblée liée", "جمعية مرتبطة"), "r_print": _t("Imprimer le registre (PDF)", "طباعة السجل (PDF)"),
    "r_fingerprint": _t("Empreinte", "البصمة"), "r_author": _t("Saisi par", "أدخله"),
}

DOCUMENTS_LABELS = {
    "doc_cat": {
        "statuts": _t("Statuts et règlement", "النظام الأساسي واللائحة"), "decision": _t("Décisions et notes", "قرارات ومذكرات"),
        "convention": _t("Conventions et partenariats", "اتفاقيات وشراكات"), "rapport": _t("Rapports", "تقارير"),
        "modele": _t("Modèles de documents", "نماذج وثائق"), "autre": _t("Autres", "أخرى"),
    },
    "courrier_sens": {"arrivee": _t("Arrivée", "وارد"), "depart": _t("Départ", "صادر")},
    "courrier_statut": {"recu": _t("Reçu", "مستلم"), "en_traitement": _t("En traitement", "قيد المعالجة"),
                        "traite": _t("Traité", "تمت معالجته"), "archive": _t("Archivé", "مؤرشف")},
    "convention_statut": {"brouillon": _t("Brouillon", "مسودة"), "soumise": _t("En attente d'avis du CA", "في انتظار رأي المجلس"),
                          "approuvee": _t("Avis favorable du CA", "رأي إيجابي للمجلس"), "rejetee": _t("Avis défavorable du CA", "رأي سلبي للمجلس"),
                          "signee": _t("Signée", "موقّعة")},
    "convention_action": {"creation": _t("Création", "إنشاء"), "soumettre": _t("Soumise au CA", "أُحيلت إلى المجلس"),
                          "avis_favorable": _t("Avis favorable", "رأي إيجابي"), "avis_defavorable": _t("Avis défavorable", "رأي سلبي"),
                          "signer": _t("Signée", "وُقّعت")},
}
