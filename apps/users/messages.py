class EmailMessages:
    INVALID_LINK = "Invalid or expired confirmation link"
    ALREADY_CONFIRMED = "Email is already confirmed"
    CONFIRMED_SUCCESS = "Email successfully confirmed"
    RESEND_SUCCESS = "If the account exists and is not yet confirmed, the email has been sent"
    EMAIL_REQUIRED = "Email is required"

    PASSWORD_RESET_SENT = "If the account exists, a password reset email has been sent"
    PASSWORD_RESET_INVALID = "Invalid or expired password reset link"
    PASSWORD_RESET_SUCCESS = "Password has been successfully changed"

    TEACHER_INVITATION_INVALID = "Invalid or expired invitation link"
    TEACHER_INVITATION_SUCCESS = "Account activated successfully"
    TEACHER_INVITATION_RESEND_SUCCESS = (
        "If a pending invitation exists for this email, it has been resent"
    )


class TeacherApplicationMessages:
    EMAIL_ALREADY_REGISTERED = "A user with this email already exists."
    DUPLICATE_APPLICATION = "An application with this email is already pending or approved."
    ALREADY_DECIDED = "This application has already been decided or is not pending."
