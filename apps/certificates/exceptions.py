class CertificatesError(Exception):
    """Base for certificate domain errors. Every message is written to be shown
    verbatim to an administrator inside a confirmation modal."""


class CertificateAlreadyExistsError(CertificatesError):
    """The student already holds a valid certificate for the course."""


class CertificateAlreadyRevokedError(CertificatesError):
    pass


class CertificateSupersededError(CertificatesError):
    """The certificate has already been replaced by a re-issue."""


class StudentNotEnrolledError(CertificatesError):
    pass


class CertificateRenderError(CertificatesError):
    """The PDF could not be produced. Issuing refuses rather than saving a row
    whose certificate_url is null, since the caller is promised a downloadable
    certificate in the 201."""


class CompletionRevertedError(CertificatesError):
    """The certificate was auto-revoked because its course completion was
    reverted, so restoring it would re-assert exactly what the revoke undid."""


class CertificateNotFoundError(CertificatesError):
    pass
