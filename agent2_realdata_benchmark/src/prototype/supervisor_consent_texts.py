"""Verbatim v1.0 consent/withdrawal strings from 12-Nov supervisor guide.

These texts are SUBMITTED FOR VALIDATION, not approved for public launch.
Do not interpolate the bracketed placeholders without PI authorization.
Versioned text must never be edited after use by real participants.
"""
CONSENT_VERSION = "v1.0"
EN_REQUIRED = (
    "I have read and understood the participant information sheet (version v1.0);",
    "I am 18 years old or over;",
    "I have never taken a course in economics or behavioral science;",
    "I understand that taking part is voluntary, has no effect on my grades, and that I can stop at any time without giving a reason;",
    "I understand that the 150 AI points are awarded only if I complete all 3 sessions;",
    "I agree that my data is processed for this research, as described in the information sheet.",
)
EN_OPTIONAL = "I agree that a fully anonymized dataset derived from my answers may be published in open access for research purposes."
FR_REQUIRED = (
    "avoir lu et compris la notice d’information (version v1.0) ;",
    "avoir 18 ans ou plus ;",
    "ne jamais avoir suivi de cours d’économie ou de sciences comportementales ;",
    "savoir que ma participation est volontaire, sans effet sur mes notes, et que je peux arrêter à tout moment sans justification ;",
    "savoir que les 150 AI points sont attribués uniquement si je termine les 3 sessions ;",
    "accepter que mes données soient traitées pour cette recherche, dans les conditions décrites dans la notice.",
)
FR_OPTIONAL = "j’accepte qu’un jeu de données entièrement anonymisé, issu de mes réponses, soit publié en accès ouvert à des fins de recherche."
INELIGIBLE = "Thank you for your interest. Unfortunately you do not meet the eligibility criteria for this study."
DUPLICATE = "This email is already registered. Use the link sent to you by email."
REGISTERED = "Registration complete. Check your inbox for your personal link."
STOP_PAGE = (
    "Stop participating\n"
    "You can stop at any time, without giving a reason. Please note: the 150 AI points are awarded only to participants who complete all 3 sessions, so no points will be awarded if you stop now.\n"
    "Choose one option:\n"
    "[ Stop and keep my answers ] Your answers so far stay in the study, under a code.\n"
    "[ Stop and delete my data ] All your answers and your email are deleted now.\n"
    "[ Cancel, I want to continue ]"
)
KEEP_CONFIRMATION = (
    "Your participation has ended. Your answers so far stay in the study under a code; "
    "your email will be deleted at the end of data collection. Thank you for your time. Contact: [email]"
)
DELETE_CONFIRMATION = (
    "Your participation has ended and all your data has been deleted. "
    "This is the last email you will receive from us. Thank you for your time. Contact: [email]"
)
DEBRIEF = (
    "Thank you for taking part in this study! There were three versions of the quiz. "
    "The first detected when you were struggling on a concept and offered you a help sequence. "
    "The second always chose the concept you knew least, without help. "
    "The third showed the questions in a fixed order, from easiest to hardest. "
    "Your version was assigned automatically, and it was not shown to you so that it would not influence your answers. "
    "Your 150 AI points will be credited by [date]. The results will be shared with participants who wish to receive them at the end of the study. "
    "For any question, or to exercise your rights: [email]."
)
TOKEN_SUBJECT = "Your link for the Self-Healing Adaptive Quiz study"
TOKEN_BODY = (
    "Hello,\n"
    "Thank you for joining our study! Here is your personal link. Use it for all 3 sessions and do not share it:\n"
    "[link]\n"
    "Session 1 can start now. Each session takes about 45 minutes. Session 2 opens 3 days after Session 1, and Session 3 opens 3 days after Session 2. We will remind you 24 hours before.\n"
    "The 150 AI points are awarded once you complete all 3 sessions.\n"
    "You can stop at any time from the \"Stop participating\" link at the bottom of every page, or by replying to this email. The information sheet is attached.\n"
    "Thank you,\n"
    "Davis, Sara and Wiam – aivancity research team\n"
    "Principal investigator: Antoun Yaacoub, [email]"
)
def required(lang: str):
    if lang == "en":
        return EN_REQUIRED, EN_OPTIONAL
    if lang == "fr":
        return FR_REQUIRED, FR_OPTIONAL
    raise ValueError("consent language must be en or fr")
