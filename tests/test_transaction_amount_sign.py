"""El formulario de movimientos manda siempre el importe en positivo y el signo se
reconstruye a partir del tipo. Para gasto/ingreso es directo, pero en un traspaso el
tipo no dice la direccion: hay que conservar el signo que ya tenia la fila.
"""

from app.models.enums import TransactionType
from app.routers.transactions import signed_amount_cents


def test_expense_is_always_negative_and_income_positive():
    assert signed_amount_cents("35,00", TransactionType.expense) == -3500
    assert signed_amount_cents("35,00", TransactionType.income) == 3500
    # Aunque el usuario escriba el signo a mano, manda el tipo.
    assert signed_amount_cents("-35,00", TransactionType.expense) == -3500
    assert signed_amount_cents("-35,00", TransactionType.income) == 3500


def test_saving_a_transfer_keeps_the_sign_it_already_had():
    # Regresion: al guardar la pata de salida de un traspaso, el importe se volvia
    # positivo (el tipo 'transfer' no entraba en ninguna rama de signo y el formulario
    # muestra el valor absoluto). Al deshacer luego el traspaso, las dos patas
    # quedaban como ingreso en vez de una salida y una entrada.
    assert signed_amount_cents("350,00", TransactionType.transfer, previous_cents=-35000) == -35000
    assert signed_amount_cents("350,00", TransactionType.transfer, previous_cents=35000) == 35000


def test_editing_a_transfer_amount_keeps_direction():
    # Cambiar el importe de la pata de salida no debe cambiar su direccion.
    assert signed_amount_cents("410,50", TransactionType.transfer, previous_cents=-35000) == -41050
    assert signed_amount_cents("410,50", TransactionType.transfer, previous_cents=35000) == 41050


def test_new_manual_transfer_defaults_to_leaving_the_account():
    # Sin fila previa no hay direccion que conservar: se asume salida.
    assert signed_amount_cents("350,00", TransactionType.transfer) == -35000
    assert signed_amount_cents("350,00", TransactionType.transfer, previous_cents=0) == -35000


def test_switching_a_flipped_transfer_back_to_expense_restores_the_negative():
    # Camino de reparacion para los movimientos que el fallo dejo en positivo:
    # editarlos y marcarlos como gasto vuelve a dejarlos negativos.
    assert signed_amount_cents("350,00", TransactionType.expense, previous_cents=35000) == -35000
