import secrets

PREFIX = "CEAT"
SUFFIX_LENGTH = 6
# Crockford-style: 0/O and 1/I/L dropped, so a serial read out over the phone
# or copied off a printed PDF cannot land on a different certificate.
ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
MAX_ATTEMPTS = 10


def generate_serial(year: int) -> str:
    """`CEAT-<year>-<6 random chars>`.

    Keeps the shape the design specifies, but the last segment is random rather
    than a zero-padded counter: the public verify endpoint answers for anyone,
    so a sequential serial would let a single leaked certificate enumerate the
    whole registry. 30^6 is ~729 million per year.
    """
    suffix = "".join(secrets.choice(ALPHABET) for _ in range(SUFFIX_LENGTH))
    return f"{PREFIX}-{year}-{suffix}"


def generate_unique_serial(year: int) -> str:
    from apps.certificates.models import Certificate

    for _ in range(MAX_ATTEMPTS):
        serial = generate_serial(year)
        # all_objects: the unique constraint spans soft-deleted rows too.
        if not Certificate.all_objects.filter(serial=serial).exists():
            return serial
    raise RuntimeError("Could not generate a unique certificate serial.")
