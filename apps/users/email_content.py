"""Per-locale copy for transactional emails, keyed by email type then locale code.

Locale codes mirror `User.LanguageChoices` / the frontend's next-intl locales
(en/uk/es/fr/de) so `user.language` can be used directly as a lookup key.
"""

DEFAULT_EMAIL_LOCALE = "en"
SUPPORTED_EMAIL_LOCALES = {"en", "uk", "es", "fr", "de"}

EMAIL_CONTENT = {
    "verification": {
        "en": {
            "subject": "Confirm your email address",
            "heading": "Confirm your email",
            "greeting": "Hi {name},",
            "paragraphs": [
                "Thanks for signing up for Nexo4You! Please confirm your email address to activate your account.",
            ],
            "cta_label": "Confirm Email",
            "expiry_note": "This link is valid for 2 days.",
            "footer_note": "If you didn't create an account, you can safely ignore this email.",
        },
        "uk": {
            "subject": "Підтвердіть свою електронну адресу",
            "heading": "Підтвердження email",
            "greeting": "Привіт, {name}!",
            "paragraphs": [
                "Дякуємо за реєстрацію на Nexo4You! Підтвердіть, будь ласка, свою електронну адресу, щоб активувати акаунт.",
            ],
            "cta_label": "Підтвердити Email",
            "expiry_note": "Посилання дійсне протягом 2 днів.",
            "footer_note": "Якщо ви не створювали цей акаунт, просто проігноруйте цей лист.",
        },
        "es": {
            "subject": "Confirma tu dirección de correo",
            "heading": "Confirma tu correo",
            "greeting": "Hola, {name}:",
            "paragraphs": [
                "¡Gracias por registrarte en Nexo4You! Confirma tu dirección de correo para activar tu cuenta.",
            ],
            "cta_label": "Confirmar Correo",
            "expiry_note": "Este enlace es válido durante 2 días.",
            "footer_note": "Si no creaste esta cuenta, puedes ignorar este correo sin problema.",
        },
        "fr": {
            "subject": "Confirmez votre adresse e-mail",
            "heading": "Confirmez votre e-mail",
            "greeting": "Bonjour {name},",
            "paragraphs": [
                "Merci de vous être inscrit(e) sur Nexo4You ! Veuillez confirmer votre adresse e-mail pour activer votre compte.",
            ],
            "cta_label": "Confirmer l'e-mail",
            "expiry_note": "Ce lien est valable pendant 2 jours.",
            "footer_note": "Si vous n'êtes pas à l'origine de cette inscription, vous pouvez ignorer cet e-mail.",
        },
        "de": {
            "subject": "Bestätigen Sie Ihre E-Mail-Adresse",
            "heading": "E-Mail bestätigen",
            "greeting": "Hallo {name},",
            "paragraphs": [
                "Danke für Ihre Registrierung bei Nexo4You! Bitte bestätigen Sie Ihre E-Mail-Adresse, um Ihr Konto zu aktivieren.",
            ],
            "cta_label": "E-Mail bestätigen",
            "expiry_note": "Dieser Link ist 2 Tage lang gültig.",
            "footer_note": "Falls Sie dieses Konto nicht erstellt haben, können Sie diese E-Mail ignorieren.",
        },
    },
    "password_reset": {
        "en": {
            "subject": "Reset your password",
            "heading": "Reset your password",
            "greeting": "Hi {name},",
            "paragraphs": [
                "We received a request to reset your password. Click the button below to choose a new one.",
            ],
            "cta_label": "Reset Password",
            "expiry_note": "This link is valid for 1 hour.",
            "footer_note": "If you didn't request this, you can safely ignore this email — your password will stay unchanged.",
        },
        "uk": {
            "subject": "Скидання пароля",
            "heading": "Скидання пароля",
            "greeting": "Привіт, {name}!",
            "paragraphs": [
                "Ми отримали запит на скидання вашого пароля. Натисніть кнопку нижче, щоб встановити новий.",
            ],
            "cta_label": "Скинути Пароль",
            "expiry_note": "Посилання дійсне протягом 1 години.",
            "footer_note": "Якщо ви не робили цей запит, просто проігноруйте лист — пароль залишиться без змін.",
        },
        "es": {
            "subject": "Restablece tu contraseña",
            "heading": "Restablece tu contraseña",
            "greeting": "Hola, {name}:",
            "paragraphs": [
                "Recibimos una solicitud para restablecer tu contraseña. Haz clic en el botón de abajo para elegir una nueva.",
            ],
            "cta_label": "Restablecer Contraseña",
            "expiry_note": "Este enlace es válido durante 1 hora.",
            "footer_note": "Si no solicitaste esto, puedes ignorar este correo: tu contraseña no cambiará.",
        },
        "fr": {
            "subject": "Réinitialisez votre mot de passe",
            "heading": "Réinitialisez votre mot de passe",
            "greeting": "Bonjour {name},",
            "paragraphs": [
                "Nous avons reçu une demande de réinitialisation de votre mot de passe. Cliquez sur le bouton ci-dessous pour en choisir un nouveau.",
            ],
            "cta_label": "Réinitialiser le mot de passe",
            "expiry_note": "Ce lien est valable pendant 1 heure.",
            "footer_note": "Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet e-mail : votre mot de passe restera inchangé.",
        },
        "de": {
            "subject": "Passwort zurücksetzen",
            "heading": "Passwort zurücksetzen",
            "greeting": "Hallo {name},",
            "paragraphs": [
                "Wir haben eine Anfrage zum Zurücksetzen Ihres Passworts erhalten. Klicken Sie auf die Schaltfläche unten, um ein neues festzulegen.",
            ],
            "cta_label": "Passwort zurücksetzen",
            "expiry_note": "Dieser Link ist 1 Stunde lang gültig.",
            "footer_note": "Falls Sie dies nicht angefordert haben, können Sie diese E-Mail ignorieren — Ihr Passwort bleibt unverändert.",
        },
    },
    "teacher_invitation": {
        "en": {
            "subject": "Congratulations! Your teacher application has been approved",
            "heading": "Welcome to the Nexo4You teaching team!",
            "greeting": "Hi {name},",
            "paragraphs": [
                "Your teacher application has been approved. Click the button below to confirm your email and set your password.",
            ],
            "cta_label": "Activate My Account",
            "expiry_note": None,
            "footer_note": "If you weren't expecting this email, please contact our support team.",
        },
        "uk": {
            "subject": "Вітаємо! Вашу заявку викладача схвалено",
            "heading": "Ласкаво просимо до команди викладачів Nexo4You!",
            "greeting": "Привіт, {name}!",
            "paragraphs": [
                "Вашу заявку на роль викладача схвалено. Натисніть кнопку нижче, щоб підтвердити email і встановити пароль.",
            ],
            "cta_label": "Активувати Акаунт",
            "expiry_note": None,
            "footer_note": "Якщо ви не очікували цього листа, звʼяжіться з нашою службою підтримки.",
        },
        "es": {
            "subject": "¡Felicidades! Tu solicitud de profesor ha sido aprobada",
            "heading": "¡Bienvenido/a al equipo docente de Nexo4You!",
            "greeting": "Hola, {name}:",
            "paragraphs": [
                "Tu solicitud para ser profesor ha sido aprobada. Haz clic en el botón de abajo para confirmar tu correo y crear tu contraseña.",
            ],
            "cta_label": "Activar Mi Cuenta",
            "expiry_note": None,
            "footer_note": "Si no esperabas este correo, contacta con nuestro equipo de soporte.",
        },
        "fr": {
            "subject": "Félicitations ! Votre candidature d'enseignant a été approuvée",
            "heading": "Bienvenue dans l'équipe pédagogique de Nexo4You !",
            "greeting": "Bonjour {name},",
            "paragraphs": [
                "Votre candidature d'enseignant a été approuvée. Cliquez sur le bouton ci-dessous pour confirmer votre e-mail et définir votre mot de passe.",
            ],
            "cta_label": "Activer Mon Compte",
            "expiry_note": None,
            "footer_note": "Si vous ne vous attendiez pas à cet e-mail, contactez notre équipe support.",
        },
        "de": {
            "subject": "Herzlichen Glückwunsch! Ihre Bewerbung als Lehrkraft wurde angenommen",
            "heading": "Willkommen im Nexo4You-Lehrteam!",
            "greeting": "Hallo {name},",
            "paragraphs": [
                "Ihre Bewerbung als Lehrkraft wurde angenommen. Klicken Sie auf die Schaltfläche unten, um Ihre E-Mail zu bestätigen und ein Passwort festzulegen.",
            ],
            "cta_label": "Konto Aktivieren",
            "expiry_note": None,
            "footer_note": "Falls Sie diese E-Mail nicht erwartet haben, wenden Sie sich bitte an unseren Support.",
        },
    },
    "teacher_application_cancelled": {
        "en": {
            "subject": "Your teacher registration application has been cancelled",
            "heading": "Application update",
            "greeting": "Hi {name},",
            "paragraphs": [
                "Unfortunately, your teacher registration application has been cancelled.",
            ],
            "cta_label": None,
            "expiry_note": None,
            "footer_note": "If you have any questions, feel free to reach out to our support team.",
            "moderator_comment_label": "Moderator comment:",
        },
        "uk": {
            "subject": "Вашу заявку на реєстрацію викладача скасовано",
            "heading": "Оновлення щодо заявки",
            "greeting": "Привіт, {name}!",
            "paragraphs": [
                "На жаль, вашу заявку на реєстрацію як викладача скасовано.",
            ],
            "cta_label": None,
            "expiry_note": None,
            "footer_note": "Якщо у вас є питання, звертайтесь до нашої служби підтримки.",
            "moderator_comment_label": "Коментар модератора:",
        },
        "es": {
            "subject": "Tu solicitud de registro como profesor ha sido cancelada",
            "heading": "Actualización de tu solicitud",
            "greeting": "Hola, {name}:",
            "paragraphs": [
                "Lamentablemente, tu solicitud de registro como profesor ha sido cancelada.",
            ],
            "cta_label": None,
            "expiry_note": None,
            "footer_note": "Si tienes alguna pregunta, no dudes en contactar con nuestro equipo de soporte.",
            "moderator_comment_label": "Comentario del moderador:",
        },
        "fr": {
            "subject": "Votre candidature d'inscription en tant qu'enseignant a été annulée",
            "heading": "Mise à jour de votre candidature",
            "greeting": "Bonjour {name},",
            "paragraphs": [
                "Malheureusement, votre candidature d'inscription en tant qu'enseignant a été annulée.",
            ],
            "cta_label": None,
            "expiry_note": None,
            "footer_note": "Pour toute question, n'hésitez pas à contacter notre équipe support.",
            "moderator_comment_label": "Commentaire du modérateur :",
        },
        "de": {
            "subject": "Ihre Bewerbung zur Lehrkraft-Registrierung wurde storniert",
            "heading": "Update zu Ihrer Bewerbung",
            "greeting": "Hallo {name},",
            "paragraphs": [
                "Leider wurde Ihre Bewerbung zur Registrierung als Lehrkraft storniert.",
            ],
            "cta_label": None,
            "expiry_note": None,
            "footer_note": "Bei Fragen wenden Sie sich gerne an unseren Support.",
            "moderator_comment_label": "Kommentar des Moderators:",
        },
    },
}


def resolve_email_locale(language: str | None) -> str:
    return language if language in SUPPORTED_EMAIL_LOCALES else DEFAULT_EMAIL_LOCALE


def get_email_content(email_type: str, language: str | None) -> dict:
    locale = resolve_email_locale(language)
    return EMAIL_CONTENT[email_type][locale]
