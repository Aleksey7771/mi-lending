from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

import config
from db.database import get_db
from db.dialogs import cancel_auto_send, mark_sent, get_dialog
from platforms.max_dialog import send_message

router = Router()


class DialogStates(StatesGroup):
    waiting_manual_reply = State()


def _notify_keyboard(dialog_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✏️ Переписать", callback_data=f"dialog_rewrite_{dialog_id}"),
        InlineKeyboardButton(text="✅ Отправить сейчас", callback_data=f"dialog_ok_{dialog_id}"),
    ]])


async def notify_owner(bot, dialog_id: int, client_name: str, question: str, bot_response: str) -> None:
    text = (
        f"💬 <b>Новый диалог в Max</b>\n"
        f"Клиент: {client_name}\n"
        f"Вопрос: {question}\n\n"
        f"Ответ бота:\n{bot_response}\n\n"
        f"<i>Автоотправка через 5 мин.</i>"
    )
    await bot.send_message(
        config.ALLOWED_USER_ID, text,
        reply_markup=_notify_keyboard(dialog_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("dialog_rewrite_"))
async def handle_dialog_rewrite(callback: CallbackQuery, state: FSMContext) -> None:
    dialog_id = int(callback.data.split("_")[-1])
    async with get_db() as db:
        await cancel_auto_send(db, dialog_id)
        row = await get_dialog(db, dialog_id)
    chat_id = row["client_id"] if row else None
    await state.update_data(pending_dialog_id=dialog_id, pending_chat_id=chat_id)
    await state.set_state(DialogStates.waiting_manual_reply)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Напишите ваш вариант ответа клиенту:")
    await callback.answer()


@router.callback_query(F.data.startswith("dialog_ok_"))
async def handle_dialog_ok(callback: CallbackQuery) -> None:
    dialog_id = int(callback.data.split("_")[-1])
    async with get_db() as db:
        row = await get_dialog(db, dialog_id)
        if row and not row["sent"] and not row["cancelled"]:
            ok = await send_message(row["client_id"], row["bot_response"])
            if ok:
                await mark_sent(db, dialog_id)
                await callback.message.answer("✅ Ответ отправлен немедленно.")
            else:
                await callback.message.answer("⚠️ Ошибка отправки в Max.")
        else:
            await callback.message.answer("ℹ️ Уже отправлен или отменён.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


@router.message(DialogStates.waiting_manual_reply)
async def handle_manual_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    dialog_id = data.get("pending_dialog_id")
    chat_id = data.get("pending_chat_id")
    reply_text = message.text or ""
    if chat_id and reply_text:
        ok = await send_message(chat_id, reply_text)
        if ok:
            async with get_db() as db:
                await mark_sent(db, dialog_id)
            await message.answer("✅ Ответ отправлен клиенту.")
        else:
            await message.answer("⚠️ Не удалось отправить в Max. Попробуйте вручную.")
    await state.clear()
