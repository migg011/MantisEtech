"""Ajuda chamadas antigas a usar os nomes atuais dos argumentos."""
from functools import wraps


def adapt_call(function, translations):
    """Troca os nomes antigos antes de chamar a função."""
    @wraps(function)
    def call(*args, **kwargs):
        translated_kwargs = {}
        for name, value in kwargs.items():
            target = translations.get(name, name)
            if target in translated_kwargs:
                raise TypeError(f'Argumento repetido: {target}')
            translated_kwargs[target] = value
        return function(*args, **translated_kwargs)
    return call
