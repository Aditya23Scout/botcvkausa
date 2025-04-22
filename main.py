import os
import math
import zipfile
import rarfile
from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram import F
import asyncio
from uuid import uuid4
from aiogram.types import Message
from datetime import datetime
import pytz


BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 1278825209

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class Form(StatesGroup):
    choosing_mode = State()
    waiting_for_txt_file = State()
    waiting_for_filename = State()
    waiting_for_contact_name = State()
    waiting_for_per_file = State()
    entering_admin = State()
    entering_navy = State()
    entering_output_filename_admin = State()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="CV Admin+Navy"))
    builder.add(types.KeyboardButton(text="CV TXT"))
    builder.add(types.KeyboardButton(text="CV ZIP/RAR"))
    await message.answer("Pilih mode:", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(Form.choosing_mode)

@dp.message(Form.choosing_mode, F.text == "CV Admin+Navy")
async def handle_mode_admin(message: Message, state: FSMContext):
    await message.answer("Masukkan nama kontak Admin (atau ketik 'cukup' jika selesai):")
    await state.update_data(admin_contacts=[])
    await state.set_state(Form.entering_admin)

@dp.message(Form.entering_admin)
async def handle_admin_input(message: Message, state: FSMContext):
    if message.text.lower() == 'cukup':
        await message.answer("Masukkan nama kontak Navy (atau ketik 'cukup' jika tidak ada):")
        await state.update_data(navy_contacts=[])
        await state.set_state(Form.entering_navy)
    else:
        parts = message.text.split(',')
        if len(parts) != 2:
            await message.answer("Format salah. Masukkan dengan format: Nama,Nomor")
            return
        name, number = parts[0].strip(), parts[1].strip()
        data = await state.get_data()
        data['admin_contacts'].append((name, number))
        await state.update_data(admin_contacts=data['admin_contacts'])
        await message.answer("Kontak admin ditambahkan. Tambahkan lagi atau ketik 'cukup' jika selesai:")

@dp.message(Form.entering_navy)
async def handle_navy_input(message: Message, state: FSMContext):
    if message.text.lower() == 'cukup':
        await message.answer("Masukkan nama file output (tanpa ekstensi):")
        await state.set_state(Form.entering_output_filename_admin)
    else:
        parts = message.text.split(',')
        if len(parts) != 2:
            await message.answer("Format salah. Masukkan dengan format: Nama,Nomor")
            return
        name, number = parts[0].strip(), parts[1].strip()
        data = await state.get_data()
        data['navy_contacts'].append((name, number))
        await state.update_data(navy_contacts=data['navy_contacts'])
        await message.answer("Kontak navy ditambahkan. Tambahkan lagi atau ketik 'cukup' jika selesai:")

@dp.message(Form.entering_output_filename_admin)
async def generate_vcf_from_manual(message: Message, state: FSMContext):
    filename = message.text
    data = await state.get_data()
    contacts = data.get('admin_contacts', []) + data.get('navy_contacts', [])
    os.makedirs("output", exist_ok=True)
    output_path = f"output/{filename}.vcf"
    with open(output_path, 'w') as vcf:
        for contact in contacts:
            name, number = contact
            if not number.startswith('+'):
                number = '+' + number
            vcf.write(f"""BEGIN:VCARD\nVERSION:3.0\nN:;{name};;;\nFN:{name}\nTEL;TYPE=CELL:{number}\nEND:VCARD\n""")
    await message.answer_document(FSInputFile(output_path))
    await message.answer("Selesai!")
    await kirim_laporan_ke_admin(message, 1)
    await state.clear()

@dp.message(Form.choosing_mode, F.text == "CV TXT")
@dp.message(Form.choosing_mode, F.text == "CV ZIP/RAR")
async def handle_file_mode(message: Message, state: FSMContext):
    await message.answer("Kirimkan file .txt, .zip, atau .rar berisi nomor kontak.")
    await state.set_state(Form.waiting_for_txt_file)

@dp.message(Form.waiting_for_txt_file, F.document.file_name.endswith((".txt", ".zip", ".rar")))
async def handle_file(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    os.makedirs("downloads", exist_ok=True)
    temp_path = f"downloads/{uuid4()}_{message.document.file_name}"
    await bot.download_file(file.file_path, temp_path)

    combined_txt_path = f"downloads/{uuid4()}_combined.txt"

    extract_path = f"downloads/extracted_{uuid4()}"
    os.makedirs(extract_path, exist_ok=True)

    if temp_path.endswith(".zip"):
        with zipfile.ZipFile(temp_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

    elif temp_path.endswith(".rar"):
        try:
            with rarfile.RarFile(temp_path) as rar:
                rar.extractall(path=extract_path)
        except Exception as e:
            await message.answer(f"Gagal mengekstrak file RAR: {e}")
            return

    if temp_path.endswith((".zip", ".rar")):
        with open(combined_txt_path, 'w') as outfile:
            for root, _, files in os.walk(extract_path):
                for file_name in sorted(files):
                    if file_name.endswith(".txt"):
                        with open(os.path.join(root, file_name), 'r', encoding='utf-8', errors='ignore') as infile:
                            outfile.write(infile.read() + "\n")
    else:
        combined_txt_path = temp_path

    with open(combined_txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [line.strip() for line in f if line.strip()]
        await message.answer(f"Jumlah kontak ditemukan: {len(lines)}")

    await state.update_data(txt_path=combined_txt_path)
    await message.answer("Masukkan nama file output (tanpa ekstensi):")
    await state.set_state(Form.waiting_for_filename)

@dp.message(Form.waiting_for_filename)
async def handle_filename(message: types.Message, state: FSMContext):
    await state.update_data(output_name=message.text)
    await message.answer("Masukkan format nama kontak, atau ketik 'otomatis' untuk menggunakan nama file sebagai dasar:")
    await state.set_state(Form.waiting_for_contact_name)

@dp.message(Form.waiting_for_contact_name)
async def handle_contact_name(message: types.Message, state: FSMContext):
    await state.update_data(contact_name=message.text)
    await message.answer("Masukkan jumlah kontak per file .vcf:")
    await state.set_state(Form.waiting_for_per_file)

@dp.message(Form.waiting_for_per_file)
async def handle_per_file(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Harus berupa angka. Masukkan jumlah kontak per file:")
        return

    per_file = int(message.text)
    data = await state.get_data()
    txt_path = data['txt_path']
    output_name = data['output_name']

    with open(txt_path, 'r') as f:
        numbers = [line.strip() for line in f if line.strip()]

    total_files = math.ceil(len(numbers) / per_file)
    os.makedirs("output", exist_ok=True)
    file_paths = []

    for i in range(total_files):
        part_numbers = numbers[i*per_file:(i+1)*per_file]
        file_base_name = f"{output_name}-{i+1}"
        filename = f"output/{file_base_name}.vcf"
        with open(filename, 'w') as vcf:
            for idx, number in enumerate(part_numbers):
                contact_name = f"{file_base_name} {str(idx + 1).zfill(3)}"
                if not number.startswith('+'):
                    number = '+' + number
                vcf.write(f"""BEGIN:VCARD\nVERSION:3.0\nN:;{contact_name};;;\nFN:{contact_name}\nTEL;TYPE=CELL:{number}\nEND:VCARD\n""")
        file_paths.append(filename)

    for file in file_paths:
        await message.answer_document(FSInputFile(file))

    await message.answer(f"Selesai! Total file: {total_files}")
    await kirim_laporan_ke_admin(message, total_files)
    await state.clear()

async def kirim_laporan_ke_admin(message: Message, jumlah_file_vcf: int):
    user = message.from_user
    username = user.username if user.username else f"{user.full_name}"

    jakarta_tz = pytz.timezone("Asia/Jakarta")
    waktu = datetime.now(jakarta_tz).strftime("%d-%m-%Y %H:%M:%S")

    teks_laporan = (
        f"🧾 Pengguna Baru Menggunakan Bot\n"
        f"👤 Username: @{username}\n"
        f"📦 Jumlah File .vcf: {jumlah_file_vcf}\n"
        f"🕒 Waktu: {waktu} WIB\n"
        f"📬 User ID: {user.id}"
    )

    await bot.send_message(chat_id=ADMIN_ID, text=teks_laporan)


if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    asyncio.run(dp.start_polling(bot))
