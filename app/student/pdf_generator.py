from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Set, Iterable

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject, DictionaryObject


TEXT_FIELD_MAP: Dict[str, str] = {
	"fio": "fill_1",
	"group": "group",
	"phone": "number",
	"email_local": "email",
	"dorm_number": "fill_2",
	"dorm_room": "fill_3",
	"date": "fill_7",
	"signature": "fill_8",
}

# Галочки (категории/ситуации/тип поддержки)
CHECKBOX_MAP: Dict[str, str] = {
	# Категории (левая колонка)
	"category_orphan": "toggle_1",						# Сирота
	"category_disabled": "toggle_3",					# Инвалид
	"category_disabled_war_trauma": "toggle_5",			# Инвалид вследствие военной травмы
	"category_chernobyl": "toggle_7",					# Чернобылец
	"category_veteran": "toggle_9",						# Ветеран боевых действий
	"category_family_injured_svo": "toggle_11",			# Семья военнослужащих/сотр., получивших увечье/заболевание при исполнении (СВО)
	"category_family_killed_svo": "toggle_13",			# Семья военнослужащих/сотр., погибших (умерших) при исполнении (СВО)
	"category_hero_rf": "toggle_15",					# Герои РФ / награжденные орденами / родители
	"category_single_parent": "toggle_17",				# Мать-одиночка / одинокий отец
	"category_young_family_with_kids": "toggle_19",		# Молодая семья, имеющая детей
	"category_children_disabled": "toggle_21",			# Имею детей-инвалидов

	# Категории (правая колонка)
	"category_young_family": "toggle_2",				# Молодая семья
	"category_pregnancy": "toggle_4",					# Постановка на учет по беременности
	"category_incomplete_family": "toggle_6",			# Неполная семья
	"category_large_family": "toggle_8",				# Многодетная семья
	"category_parent_disabled": "toggle_10",			# Родитель(-и) инвалид(ы)
	"category_parent_pensioner": "toggle_12",			# Родитель(-и) пенсионер(ы)
	"category_dispanser": "toggle_14",					# Состою на диспансерном учете
	"category_donor": "toggle_16",						# Донор
	"category_nonresident_no_dorm": "toggle_18",		# Иногородний, не проживаю в общежитии
	"category_achievements": "toggle_20",				# Достижения (конкурсы, гранты и т.п.)
	"category_nonresident_in_dorm": "toggle_22",		# Иногородний, проживаю в общежитии

	# Особые случаи
	"case_death_relative": "toggle_23",					# Смерть близкого родственника
	"case_birth_child": "toggle_24",					# Рождение ребенка
	"case_death_relative_svo": "toggle_25",				# Смерть близкого родственника при исполнении (СВО)
	"case_disease_trauma": "toggle_26",					# Заболевание/травма/операция, расходы на лечение
	"case_marriage": "toggle_27",						# Вступление в брак
	"case_emergency": "toggle_28",						# ЧС/беженец/жертва обстоятельств

	# Вид материальной поддержки
	"support_one_time": "toggle_29",					# Единовременная мат.поддержка
	"support_travel": "toggle_30",						# Компенсация стоимости проезда (общая галочка)
	"support_travel_home": "toggle_31",					# До места жительства
	"support_travel_treatment": "toggle_32",			# До места лечения/санаторно-курортного отдыха
	"support_dorm_payment": "toggle_33",				# Компенсация проживания в общежитии
}


@dataclass(frozen=True)
class MPProfile:
	fio: str
	group: str
	phone: str
	email_local: str
	dorm_number: str
	dorm_room: str
	date: str
	signature: str


def _set_need_appearances(writer: PdfWriter) -> None:
	root = writer._root_object
	if "/AcroForm" not in root:
		root[NameObject("/AcroForm")] = DictionaryObject()

	acro = root["/AcroForm"]
	if hasattr(acro, "get_object"):
		acro = acro.get_object()

	acro[NameObject("/NeedAppearances")] = BooleanObject(True)


def _get_checkbox_on_state(annot_obj) -> NameObject:
	ap = annot_obj.get("/AP")
	if ap and "/N" in ap:
		n = ap["/N"]
		for k in n.keys():
			if str(k) != "/Off":
				return k
	return NameObject("/Yes")


def fill_mp_pdf(
	input_pdf: Path,
	output_pdf: Path,
	profile: MPProfile,
	selected: Iterable[str],
) -> None:
	"""
	selected: список семантических ключей из CHECKBOX_MAP
	например: ["category_achievements", "support_one_time"]
	"""
	selected_keys: Set[str] = set(selected)

	reader = PdfReader(str(input_pdf))

	# Сначала проставляем галочки прямо в аннотациях (Widget)
	selected_toggle_names: Set[str] = set()
	for key in selected_keys:
		if key not in CHECKBOX_MAP:
			# Можно логировать или игнорировать, но лучше знать
			print(f"Warning: Unknown checkbox key: {key}")
			continue
		selected_toggle_names.add(CHECKBOX_MAP[key])

	for page in reader.pages:
		annots = page.get("/Annots")
		if not annots:
			continue

		for a in annots:
			obj = a.get_object()
			if obj.get("/Subtype") != "/Widget":
				continue

			name = obj.get("/T")
			if not name:
				continue

			name_str = str(name)

			# Все toggle_* принудительно сбрасываем в Off, чтобы не было "залипаний"
			if name_str.startswith("toggle_"):
				obj[NameObject("/V")] = NameObject("/Off")
				obj[NameObject("/AS")] = NameObject("/Off")

			# Те, что выбраны — включаем
			if name_str in selected_toggle_names:
				on_state = _get_checkbox_on_state(obj)
				obj[NameObject("/V")] = on_state
				obj[NameObject("/AS")] = on_state

	# Текстовые поля
	text_values: Dict[str, str] = {
		TEXT_FIELD_MAP["fio"]: profile.fio,
		TEXT_FIELD_MAP["group"]: profile.group,
		TEXT_FIELD_MAP["phone"]: profile.phone,
		TEXT_FIELD_MAP["email_local"]: profile.email_local,
		TEXT_FIELD_MAP["dorm_number"]: profile.dorm_number,
		TEXT_FIELD_MAP["dorm_room"]: profile.dorm_room,
		TEXT_FIELD_MAP["date"]: profile.date,
		TEXT_FIELD_MAP["signature"]: profile.signature,
	}

	writer = PdfWriter()
	writer.clone_reader_document_root(reader)

	_set_need_appearances(writer)

	for page in writer.pages:
		writer.update_page_form_field_values(page, text_values)

	output_pdf.parent.mkdir(parents=True, exist_ok=True)
	with open(output_pdf, "wb") as f:
		writer.write(f)
