// French (fr-FR) translation set for the MarkMyAss homepage.
//
// English is the source language (the literal HTML in index.html), so this
// file only needs to exist for fr-FR. Keys match the `data-i18n` /
// `data-i18n-attr` markers in index.html one-for-one; tests/test_i18n.py
// asserts full coverage so the French UI is never partial (no mixed-language
// UI). Values for `data-i18n` may contain inline HTML (applied via
// innerHTML); values for `data-i18n-attr` are plain text (applied via
// setAttribute).
(function () {
  "use strict";

  var dict = {
    "meta.title": "Suppresseur de filigrane Claude & nettoyeur de métadonnées IA | MarkMyAss",

    "a11y.skip": "Aller au contenu principal",
    "promo.top": "Un projet open source par <a href='https://moseisley.sh/?utm_source=markmyass&amp;utm_medium=top&amp;utm_campaign=acquisition' rel='noopener'>Moseisley</a>",

    "nav.cleaner": "Nettoyeur",
    "nav.lab": "Labo des filigranes IA",
    "nav.runlocal": "Exécuter les modèles en local",
    "nav.crew.aria": "Obtenez votre équipage IA",
    "nav.crew.full": "Obtenez votre équipage IA →",
    "nav.crew.short": "Équipage IA →",
    "lang.switch.aria": "Langue",

    "hero.h1": "Suppresseur de filigrane Claude &amp; nettoyeur de provenance IA",
    "hero.socialproof": "fichiers nettoyés avec MarkMyAss",
    "hero.flow.inspect": "Inspecter",
    "hero.flow.clean": "Nettoyer",
    "hero.flow.verify": "Vérifier",
    "hero.subheadline": "MarkMyAss montre exactement ce qu'il a supprimé — et ce qu'il ne peut pas vérifier.",
    "hero.tagline": "Des preuves, pas des promesses.",
    "hero.cta.inspect": "Inspecter un fichier",
    "hero.cta.lab": "Explorer le Labo",
    "hero.trust.free": "Gratuit",
    "hero.trust.oss": "Open source",
    "hero.trust.noaccount": "Sans compte",
    "hero.trust.independent": "Vérification indépendante",
    "hero.trust.download": "Téléchargez votre fichier nettoyé",
    "hero.honesty": "Pas de faux scores « 100 % indétectable ».",
    "hero.scene.alt": "Illustration d'un équipage de pirates à bord de son navire : le capitaine verrouille un faisceau de longue-vue lumineux sur un fantôme surpris, un membre d'équipage attrape au filet un fantôme en fuite, un autre découvre un fantôme caché dans un coffre au trésor en riant et en pointant du doigt une marque de crâne estampée sur le pantalon du lanceur de filet",

    "llm.h2": "Fonctionne au-delà de Claude",
    "llm.lead": "Supprimez les filigranes IA pris en charge, les métadonnées et les traces cachées de vos images, textes, PDF et documents IA — avant de les publier.",
    "llm.fine": "Quelle que soit l'IA qui l'a créé, MarkMyAss inspecte, nettoie et vérifie les signaux pris en charge à l'intérieur du fichier. Les filigranes statistiques au niveau du modèle restent honnêtement marqués INCONNU — jamais déclarés supprimés.",

    "tool.flavor.input": "Voyons ce qui se cache à l'intérieur.",
    "tool.tab.text": "Coller du texte",
    "tool.tab.file": "Téléverser un fichier",
    "tool.formats": "Formats acceptés : TXT · MD · JSON · CSV · JPG · JPEG · PNG · WEBP · PDF",
    "tool.placeholder": "Collez le texte à inspecter...",
    "tool.dropzone.drag": "Glissez un fichier ici",
    "tool.dropzone.or": "ou",
    "tool.dropzone.choose": "Choisir un fichier",
    "tool.file.hint": "Images (JPG, JPEG, PNG, WebP), PDF et fichiers texte (TXT, MD, JSON, CSV).",
    "tool.btn.inspect": "Inspecter",

    "tool.step1": "ÉTAPE 1 — INSPECTION",
    "tool.flavor.inspect": "Repérez les fantômes — on scanne la cargaison à la recherche de signaux cachés.",
    "tool.scopenote": "Vérifie les signaux pris en charge au niveau du fichier (EXIF · XMP · texte PNG · C2PA). Les filigranes statistiques au niveau du modèle comme SynthID ne sont pas vérifiables localement pour l'instant — leur absence n'est jamais affirmée.",
    "tool.explain.title": "Ce que cela signifie",
    "tool.btn.clean": "Nettoyer le fichier",

    "tool.step2": "ÉTAPE 2 — NETTOYAGE",
    "tool.flavor.clean": "Videz le pont — on retire les traces prises en charge.",
    "tool.cleanedtext": "Texte nettoyé",
    "tool.preserved": "Fichier original <strong>CONSERVÉ</strong> — MarkMyAss ne modifie jamais votre original.",
    "tool.btn.verify": "Vérifier de façon indépendante",
    "tool.btn.reprocessopen": "Retraitement profond →",

    "tool.step3": "ÉTAPE 3 — VÉRIFICATION INDÉPENDANTE",
    "tool.flavor.verify": "Un second observateur contrôle le travail.",
    "tool.before": "Avant",
    "tool.after": "Après",
    "tool.verify.watermarknote": "Métadonnées / provenance du fichier : <strong>pris en charge</strong> &middot; Filigrane statistique au niveau du modèle (Claude / Gemini / GPT) : <strong>PAS ENCORE VÉRIFIABLE</strong> &middot; <a href='lab/claude-watermark'>pourquoi ? →</a>",
    "tool.flavor.cargo": "Cargaison dégagée. Votre cargaison nettoyée est prête.",
    "tool.btn.save": "Télécharger le fichier propre",
    "tool.receipt.label": "Reçu de vérification :",
    "tool.labteaser": "Curieux de savoir ce que MarkMyAss peut et ne peut pas vérifier ? <a href='lab'>Explorez le Labo des filigranes IA →</a>",
    "tool.moseisley.kicker": "Votre fichier est propre.",
    "tool.moseisley.h3": "Envie de tout l'équipage ?",
    "tool.moseisley.p": "MarkMyAss n'est qu'un outil. Moseisley vous donne votre propre équipe d'agents et d'assistants IA.",
    "tool.moseisley.btn": "Commencer gratuitement sur Moseisley →",

    "tool.reprocess.h2": "RETRAITEMENT PROFOND",
    "tool.flavor.reprocess": "Retaillez le bois — construisez une toute nouvelle représentation en pixels de votre image.",
    "tool.reprocess.disclaimer": "Crée une nouvelle représentation en pixels de votre image. Cela peut affecter les signaux intégrés au niveau des pixels, mais MarkMyAss ne <strong>garantit pas</strong> la suppression des filigranes statistiques comme SynthID.",
    "tool.reprocess.intensity": "Intensité",
    "tool.reprocess.outformat": "Format de sortie",
    "tool.reprocess.keepsource": "Conserver la source",
    "tool.reprocess.run": "Retraiter l'image",
    "tool.reprocess.fileh3": "Signaux au niveau du fichier (revérifiés après retraitement)",
    "tool.reprocess.pixelh3": "Changement au niveau des pixels",
    "tool.reprocess.ssimhint": "Le SSIM/PSNR décrivent l'ampleur du changement des pixels — ce ne sont pas une preuve d'identité visuelle.",
    "tool.reprocess.watermarknote": "Filigrane statistique au niveau du modèle (SynthID / Claude / GPT) : <strong>NON VÉRIFIABLE LOCALEMENT</strong> &middot; le retraitement ne garantit pas la suppression.",
    "tool.reprocess.download": "Télécharger l'image retraitée",

    "skill.h2": "Utilisez MarkMyAss automatiquement",
    "skill.p": "Installez MarkMyAss dans votre flux de travail IA et laissez l'équipage inspecter, nettoyer et vérifier les traces prises en charge au fil de votre création.",
    "skill.btn": "Installer le Skill →",

    "removes.h2": "Ce que MarkMyAss supprime réellement",
    "removes.flavor": "Basé sur les signaux, pas sur la magie du fournisseur — la prise en charge dépend du type de signal, pas seulement de l'IA qui a créé le fichier.",
    "removes.good.h3": "Pris en charge de façon fiable",
    "removes.good.li1": "Unicode caché et caractères de texte invisibles",
    "removes.good.li2": "Métadonnées EXIF / XMP / IPTC (JPEG, PNG, WebP)",
    "removes.good.li3": "Métadonnées de document PDF (DocInfo + XMP)",
    "removes.good.li4": "Métadonnées PNG",
    "removes.good.li5": "Signaux de provenance pris en charge au niveau du fichier",
    "removes.good.li6": "Vérification indépendante des métadonnées avec ExifTool",
    "removes.limit.h3": "Limites actuelles",
    "removes.limit.li1": "La prise en charge C2PA / Content Credentials est partielle",
    "removes.limit.li2": "Les filigranes statistiques au niveau du modèle de Claude, Gemini et GPT sont actuellement <strong>INCONNUS</strong> — aucun vérificateur public n'existe pour confirmer leur suppression",
    "removes.limit.li3": "MarkMyAss ne prétend jamais « 100 % indétectable par l'IA »",
    "removes.vc.h3": "Ce que signifie « VÉRIFIÉ PROPRE »",
    "removes.vc.p": "MarkMyAss affiche <strong>VÉRIFIÉ PROPRE</strong> uniquement lorsqu'un signal pris en charge a réellement été trouvé avant le nettoyage, que sa propre réinspection confirme qu'il a disparu, et que chaque vérificateur indépendant ayant pu s'exécuter (ExifTool, et c2patool le cas échéant) est d'accord également. Ce n'est pas une affirmation selon laquelle le fichier ne contient aucun signal identifiant possible — seulement que les catégories de métadonnées spécifiques et prises en charge que vise MarkMyAss sont confirmées supprimées de façon indépendante. Consultez le <a href='lab'>Labo des filigranes IA</a> pour la matrice de capacités complète, notée en toute honnêteté.",
    "removes.onlyclaude.h3": "MarkMyAss est-il uniquement pour Claude ?",
    "removes.onlyclaude.p": "Non. MarkMyAss ne se limite pas à Claude. Il fonctionne avec les types de signaux de filigrane et de provenance pris en charge, y compris l'Unicode caché et les métadonnées de fichier courantes. Sa prise en charge dépend du type de signal, pas seulement du fournisseur d'IA.",

    "synthid.h2": "Qu'est-ce que SynthID ? Les métadonnées face au filigrane à l'intérieur de l'image",
    "synthid.flavor": "Une image IA peut porter deux types très différents de « marque IA ». MarkMyAss est honnête sur celle qu'il peut réellement toucher.",
    "synthid.file.tag": "NIVEAU FICHIER",
    "synthid.file.h3": "Métadonnées &amp; Content Credentials",
    "synthid.file.p": "EXIF · XMP · texte PNG · C2PA / Content Credentials — des informations stockées <em>à côté</em> de l'image.",
    "synthid.file.verdict": "MarkMyAss peut inspecter &amp; nettoyer les signaux pris en charge.",
    "synthid.content.tag": "NIVEAU CONTENU",
    "synthid.content.p": "Un filigrane invisible que Google intègre <em>dans les pixels mêmes de l'image</em> pour indiquer que le contenu a été généré ou modifié par l'IA — une technologie distincte des métadonnées ordinaires.",
    "synthid.content.verdict": "Supprimer les métadonnées ne supprime pas nécessairement SynthID — et MarkMyAss ne prétend pas le supprimer.",
    "synthid.p1": "Google a conçu <a href='https://deepmind.google/models/synthid/' rel='noopener'>SynthID</a> pour les images afin qu'il reste détectable après des modifications courantes telles que le <strong>redimensionnement, la recoloration, le recadrage, le filtrage et la compression avec perte</strong>, et affirme qu'il reste détectable même lorsque les métadonnées d'un fichier sont retirées. Son objectif publié est la <strong>provenance du contenu</strong> — répondre à « ce contenu a-t-il été généré ou modifié par l'IA ? » <strong>Google décrit SynthID comme un filigrane de provenance de contenu, pas comme un identifiant de suivi personnel</strong> ; sa documentation ne décrit pas SynthID comme contenant votre nom, votre compte Google, votre adresse IP ou l'historique de vos requêtes.",
    "synthid.realcheck.h3": "Un vrai test que nous avons mené",
    "synthid.realcheck.p1": "Nous avons généré une image avec le modèle d'image Gemini de Google et l'avons passée dans MarkMyAss. Il a trouvé la provenance <strong>au niveau du fichier</strong> de Google — XMP, texte PNG et un manifeste C2PA — et <em>Nettoyer</em> a supprimé ces signaux pris en charge, si bien qu'une seconde inspection a montré <strong>0 signal pris en charge au niveau du fichier</strong>. Nous avons ensuite téléversé cette même image nettoyée vers Gemini, qui a répondu : <em>« D'après l'analyse du filigrane numérique, tout ou partie de cette image a été créée ou modifiée à l'aide de l'IA de Google. »</em>",
    "synthid.realcheck.p2": "Après que MarkMyAss a supprimé la provenance prise en charge au niveau du fichier et qu'une seconde inspection a montré 0 signal pris en charge au niveau du fichier, Gemini a tout de même identifié l'image comme créée ou modifiée à l'aide de l'IA de Google d'après l'analyse du filigrane numérique. Cela est cohérent avec un filigrane <strong>au niveau du contenu</strong> subsistant tel que SynthID, distinct des métadonnées — même si cela ne prouve pas que SynthID seul en soit responsable. Nettoyer les métadonnées n'équivaut pas à supprimer SynthID — nous ne prétendons donc pas le contraire.",
    "synthid.euact.h3": "Pourquoi cela existe — le règlement européen sur l'IA (en clair)",
    "synthid.euact.p": "À partir du <strong>2 août 2026</strong>, l'<a href='https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50' rel='noopener'>article 50</a> du règlement européen sur l'IA demande aux fournisseurs d'IA générative de veiller à ce que les sorties synthétiques audio, image, vidéo ou texte soient «&nbsp;<em>marquées dans un format lisible par machine et détectables comme générées ou manipulées artificiellement</em>&nbsp;». Il vise le <strong>résultat</strong> (la détectabilité) et <strong>n'impose pas SynthID</strong> — SynthID est l'approche technique propre à Google, pas une norme européenne. L'article&nbsp;50(2) prévoit aussi une exception lorsque l'IA remplit «&nbsp;<em>une fonction d'assistance pour la mise en forme standard</em>&nbsp;» ou ne modifie pas de manière substantielle le contenu ou son sens. Ceci est fourni à titre d'information, pas comme un conseil juridique.",

    "writing.h2": "Gardez votre écriture à vous après une édition assistée par l'IA",
    "writing.flavor": "C'est vous qui l'avez écrit. L'IA n'a fait qu'aider à l'éditer. Voyez exactement ce qui a changé.",
    "writing.human.tag": "ÉCRITURE HUMAINE",
    "writing.human.h3": "Vos mots d'origine",
    "writing.human.p": "Les idées, la structure et la formulation que vous avez réellement écrites.",
    "writing.ai.tag": "ÉDITION PAR L'IA",
    "writing.ai.h3": "Corrections &amp; réécritures",
    "writing.ai.p": "Relecture, orthographe, grammaire, ponctuation et légère révision — ou des réécritures plus importantes.",
    "writing.p1": "Utiliser l'IA uniquement pour <strong>relire, corriger l'orthographe/la grammaire/la ponctuation ou légèrement réviser</strong> est fondamentalement différent du fait de laisser l'IA <strong>générer ou réécrire de façon substantielle</strong> votre document — une distinction que l'exception «&nbsp;mise en forme standard&nbsp;» de l'article&nbsp;50(2) du règlement sur l'IA reconnaît elle aussi.",
    "writing.p2": "Le <a href='https://ai.google.dev/responsible/docs/safeguards/synthid' rel='noopener'>SynthID-Text</a> de Google est un filigrane statistique créé <em>pendant la génération des jetons</em> en ajustant légèrement les probabilités de sélection des jetons du modèle. Ce n'est <strong>pas</strong> une métadonnée ordinaire attachée à votre fichier — il réside dans le motif des mots générés eux-mêmes, et dépend de la part du texte réellement générée par le modèle.",
    "writing.helps.h3": "Ce que MarkMyAss aide les rédacteurs à faire",
    "writing.helps.p": "Comparez votre <strong>brouillon original</strong> avec la <strong>version éditée par l'IA</strong> et voyez quelles formulations sont restées les vôtres, lesquelles étaient des corrections mécaniques et lesquelles étaient des réécritures substantielles par l'IA — afin de préserver ou de restaurer votre propre voix. <strong>MarkMyAss ne supprime pas le SynthID-Text de Google</strong> ; il vous aide à distinguer la formulation écrite par un humain d'une réécriture substantielle par l'IA. Conçu pour les auteurs, journalistes, étudiants, éditeurs, rédacteurs et chercheurs.",
    "writing.example.aria": "Exemple illustratif uniquement, pas des valeurs mesurées",
    "writing.example.badge": "EXEMPLE UNIQUEMENT — mise en page illustrative",
    "writing.example.row1": "Formulation d'origine de l'auteur",
    "writing.example.row2": "Corrections mécaniques",
    "writing.example.row3": "Réécriture substantielle par l'IA",
    "writing.example.hint": "Ces chiffres ne sont qu'un exemple de mise en page — jamais affichés comme réels sauf s'ils sont calculés à partir de votre document réel.",
    "writing.research.h3": "Notre recherche locale : quelle quantité de texte généré par l'IA le filigrane nécessite-t-il ?",
    "writing.research.caveat": "<strong>Ce sont des résultats de recherche locale de MarkMyAss utilisant nos propres clés SynthID et notre configuration de référence. Ce ne sont PAS des mesures du détecteur de production privé de Google, et ils ne s'appliquent pas directement à Gemini.</strong>",
    "writing.research.p1": "Réplication sur <strong>5 clés SynthID indépendantes × 5 graines de génération × documents d'environ 250 / 500 / 900 jetons</strong>, à l'aide d'une implémentation de référence locale (distilgpt2 comme vecteur de génération) et du détecteur Weighted-Mean sans réglage. Fraction contiguë générée par l'IA → taux de détection local :",
    "writing.research.f5": "5 % IA",
    "writing.research.sum1": "<strong>≤ 10 % de contenu généré par l'IA :</strong> majoritairement non détecté dans notre configuration locale",
    "writing.research.sum2": "<strong>~ 15–30 % :</strong> zone de transition",
    "writing.research.sum3": "<strong>≥ 40–50 % :</strong> couramment / fortement détecté",
    "writing.research.p2": "Notre seuil de détection à 50 % mesuré se situait autour de <strong>21 % d'IA</strong> pour une plage contiguë et de <strong>27 %</strong> pour des blocs dispersés. Méthode &amp; données complètes : <a href='https://github.com/bens777/MarkMyAss/tree/main/research/synthid_text_study' rel='noopener'>étude 1</a>, <a href='https://github.com/bens777/MarkMyAss/tree/main/research/synthid_text_inverse_study' rel='noopener'>étude inverse</a>, <a href='https://github.com/bens777/MarkMyAss/tree/main/research/synthid_text_replication_study' rel='noopener'>réplication</a>.",

    "usecases.h2": "Meilleurs cas d'usage",
    "usecases.flavor": "Là où MarkMyAss est vraiment fiable — pas un effaceur universel de détection d'IA, mais solide dans ce qu'il fait réellement.",
    "usecases.li1": "Nettoyer les métadonnées avant de publier des PDF ou des images",
    "usecases.li2": "Supprimer l'auteur, le créateur, le GPS et les champs de métadonnées associés",
    "usecases.li3": "Nettoyer l'Unicode caché d'un texte IA copié-collé",
    "usecases.li4": "Vérifier les fichiers pour détecter les métadonnées de provenance prises en charge avant de vous y fier",
    "usecases.li5": "Vérifier de façon indépendante que les traces prises en charge ont réellement été supprimées — sans vous fier à la parole d'un seul outil",

    "preview.aria": "Explorer MarkMyAss",
    "preview.lab.h3": "Labo des filigranes IA",
    "preview.lab.p": "Cartographiez les eaux de la provenance IA — la matrice de capacités complète, notée en toute honnêteté : vérifié, partiel ou inconnu.",
    "preview.lab.link": "Explorer le Labo →",
    "preview.bench.h3": "Benchmarks",
    "preview.bench.p": "Journal de bord du capitaine — chaque test pris en charge, chaque échec, généré à neuf à partir du vrai pipeline. Rien de caché.",
    "preview.bench.link": "Lire le journal →",
    "preview.runlocal.h3": "Exécuter les modèles en local",
    "preview.runlocal.p": "Naviguez sur votre propre stack — exécutez vous-même des modèles IA à poids ouverts et évitez la provenance côté fournisseur à la source.",
    "preview.runlocal.link": "Naviguez sur votre stack →",

    "crew.h2": "D'un seul outil à tout un équipage",
    "crew.p": "MarkMyAss nettoie les traces cachées de votre contenu IA. <a href='https://moseisley.sh/?utm_source=markmyass&amp;utm_medium=homepage&amp;utm_campaign=acquisition' rel='noopener'>Moseisley</a> vous donne un équipage personnel d'agents et d'assistants IA pour vous aider à travailler, faire des recherches, planifier et automatiser.",
    "crew.tagline": "MarkMyAss nettoie vos fichiers IA. Moseisley vous donne tout l'équipage.",
    "crew.btn": "Constituez votre équipage IA — gratuit →",

    "footer.p1": "MarkMyAss est open source (MIT), propulsé par le moteur GhostMark. <a href='https://github.com/bens777/MarkMyAss' rel='noopener'>Code source sur GitHub</a>.",
    "footer.p2": "MarkMyAss est développé par <a href='https://moseisley.sh/?utm_source=markmyass&amp;utm_medium=footer&amp;utm_campaign=acquisition' rel='noopener'>Moseisley</a>.",
    "footer.ecosystem": "<a href='https://magicconnect.ai/?utm_source=markmyass&amp;utm_medium=footer&amp;utm_campaign=ecosystem' rel='noopener'>MagicConnect.ai</a> — les conversations clients IA, automatisées.",
    "footer.sitemap.aria": "Plus de pages MarkMyAss",
    "footer.link.clauderemover": "Suppresseur de filigrane Claude",
    "footer.link.claudedetector": "Détecteur de filigrane Claude",
    "footer.link.airemover": "Suppresseur de filigrane IA",
    "footer.link.metadata": "Nettoyeur de métadonnées IA",
    "footer.link.c2pa": "Suppresseur C2PA",
    "footer.link.contentcred": "Suppresseur de Content Credentials",
    "footer.link.unicode": "Suppresseur d'Unicode caché",
    "footer.discord.aria": "Rejoindre la communauté Discord de MarkMyAss",
    "footer.discord.alt": "Pirate regardant dans une longue-vue",
    "footer.discord.label": "Rejoindre l'équipage →",
  };

  // French labels/descriptions for the Deep Reprocess intensity selector,
  // keyed by the server-side profile name. app.js uses these when the active
  // locale is fr-FR so the dropdown never drifts into English.
  var reprocessProfilesFr = {
    light: {
      label: "Léger",
      description: "Ré-encodage haute fidélité. Sans rééchantillonnage ; espace colorimétrique source préservé.",
    },
    medium: {
      label: "Moyen",
      description: "Retraitement modéré : un léger aller-retour de rééchantillonnage plus une normalisation colorimétrique sRGB, tout en restant visuellement très proche.",
    },
    strong: {
      label: "Fort",
      description: "Reconstruction plus poussée : un aller-retour de rééchantillonnage plus important et une normalisation colorimétrique sRGB, tout en gardant l'image visuellement utilisable.",
    },
  };

  if (typeof window !== "undefined") {
    window.MarkMyAss = window.MarkMyAss || {};
    window.MarkMyAss.dict = dict;
    window.MarkMyAss.reprocessProfilesFr = reprocessProfilesFr;
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { dict: dict, reprocessProfilesFr: reprocessProfilesFr };
  }
})();
