# i18n.py
import gettext
import builtins

from gettext import gettext as _

def init_locale(domain: str, locale_dir: str, lang_code: str):
    """
    Bind _() to the real gettext.gettext (or a fallback) for the given domain.
    """
    try:
        tr = gettext.translation(
            domain=domain,
            localedir=locale_dir,
            languages=[lang_code],
            fallback=False,    # will throw if .mo not found
        )
    except (FileNotFoundError, OSError):
        # fallback to the builtin gettext (which is identity)
        gettext.install(domain=domain)
        real_gettext = gettext.gettext
    else:
        # install() writes to builtins._ *and* returns the function
        tr.install()
        real_gettext = tr.gettext

    # Override our module‐level _ and the builtins one too
    globals()['_'] = real_gettext
    builtins._ = real_gettext
