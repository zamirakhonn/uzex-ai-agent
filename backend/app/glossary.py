from __future__ import annotations

GLOSSARY: list[dict[str, str]] = [
    {
        "id": "status_new",
        "uz": "Yangi (Новый) holat — bitim oxirgi yuklama kuni, 2026-yil 30-oktabrda tuzilgan.",
        "ru": "Статус «Новый» означает, что сделка заключена в последний день выгрузки — 30.10.2026.",
        "keys": "новый yangi last day 30.10.2026 holat status",
    },
    {
        "id": "status_unsigned",
        "uz": "Imzolanmagan (Не подписан) — tomonlar shartnomani hali imzolamagan.",
        "ru": "Статус «Не подписан» — договор ещё не подписан сторонами.",
        "keys": "не подписан imzolanmagan unsigned",
    },
    {
        "id": "status_signed",
        "uz": "Tuzilgan (Заключен) — forvard yoki fyuchers imzolangan, to'lov muddati hali o'tmagan.",
        "ru": "Статус «Заключен» — форвард или фьючерс подписан, срок оплаты ещё не истёк.",
        "keys": "заключен tuzilgan форвард фьючерс",
    },
    {
        "id": "status_wait_pay",
        "uz": "To'lov kutilmoqda (Ждёт оплату) — spot imzolangan, to'lov muddati o'tmagan.",
        "ru": "Статус «Ждёт оплату» — спот подписан, срок оплаты ещё не истёк.",
        "keys": "ждёт оплату wait payment to'lov",
    },
    {
        "id": "status_paid",
        "uz": "To'langan (Оплачен) — to'lov qilingan, tovar hali yetkazilmagan.",
        "ru": "Статус «Оплачен» — оплачен, товар ещё не поставлен.",
        "keys": "оплачен to'langan paid",
    },
    {
        "id": "status_done",
        "uz": "Ijro etilgan (Исполнен) — to'langan va to'liq yetkazilgan.",
        "ru": "Статус «Исполнен» — оплачен и поставлен полностью.",
        "keys": "исполнен ijro executed completed",
    },
    {
        "id": "status_partial",
        "uz": "Qisman ijro (Исполнен(Частично)) — to'langan, qismi yetkazilgan. Hajm «Поставлено» ustunida.",
        "ru": "Статус «Исполнен(Частично)» — оплачен, поставлена часть. Объём в колонке «Поставлено».",
        "keys": "частично qisman partial поставлено",
    },
    {
        "id": "status_cancel",
        "uz": "Bekor qilingan (Аннулирован(Не оплачен)) — muddatida to'lanmagan, bitim amalga oshmagan.",
        "ru": "Статус «Аннулирован(Не оплачен)» — не оплачен в срок, сделка не состоялась.",
        "keys": "аннулирован bekor cancelled unpaid",
    },
    {
        "id": "volume_rule",
        "uz": "Bitim hajmi o'lchov birligida = Количество × Лот. Birlik narxi = Сумма сделки ÷ (Количество × Лот).",
        "ru": "Объём сделки в единицах измерения = Количество × Лот. Цена за единицу = Сумма сделки ÷ (Количество × Лот).",
        "keys": "hajm объём количество лот цена за единицу hisoblash",
    },
    {
        "id": "fx_rule",
        "uz": "Eksport bitimlari AQSh dollarida. So'mdagi summa = bitim summasi × shu kundagi USD kursi (usd_rates.csv).",
        "ru": "Экспортные сделки в долларах США. Сумма в сумах = сумма сделки × курс на дату сделки из usd_rates.csv.",
        "keys": "курс доллар usd so'm сум экспорт валюта",
    },
    {
        "id": "auction_en",
        "uz": "Ingliz auksioni (Английский аукцион) — narx boshlang'ich narxdan oshadi.",
        "ru": "Английский аукцион — цена растёт от стартовой.",
        "keys": "английский аукцион ingliz auction",
    },
    {
        "id": "auction_rev",
        "uz": "Teskari auksion (Обратный аукцион) — narx boshlang'ich narxdan pasayadi.",
        "ru": "Обратный аукцион — цена снижается от стартовой.",
        "keys": "обратный аукцион teskari reverse",
    },
    {
        "id": "auction_bi",
        "uz": "Ikki tomonlama auksion (Двусторонний аукцион) — datasetdagi savdo turi.",
        "ru": "Двусторонний аукцион — вид торгов в датасете.",
        "keys": "двусторонний ikki tomonlama",
    },
    {
        "id": "kind_form",
        "uz": "Тип контракта: Ichki (Внутренний) yoki Eksport (Экспортный). Форма контракта: Spot, Forvard, Fyuchers.",
        "ru": "Тип контракта: Внутренний или Экспортный. Форма контракта: Спот, Форвард или Фьючерс.",
        "keys": "внутренний экспортный спот форвард фьючерс forma tur",
    },
]
