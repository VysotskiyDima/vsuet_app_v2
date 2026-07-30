/**
 * Константы приложения: адрес API, справочники, ключи хранилища.
 * Модуль ни от чего не зависит — его можно импортировать откуда угодно.
 */

// На порту 3000 фронт отдаётся отдельным статик-сервером в режиме отладки,
// а бек живёт на 8000. В проде оба за одним nginx, поэтому путь относительный.
export const API_BASE =
  window.location.port === "3000" ? `http://${window.location.hostname}:8000` : "";

/** Разделы рейтинга: сегмент URL API, заголовок секции и вид таблицы. */
export const VED_TYPES = [
  { segment: "zachet",             title: "Зачёт",              kind: "rating" },
  { segment: "ekzamen",            title: "Экзамен",            kind: "rating" },
  { segment: "vypusknaya-rabota",  title: "Выпускная работа",   kind: "grade"  },
  { segment: "gosekzamen",         title: "ГосЭкзамен",         kind: "grade"  },
  { segment: "kontrolnaya-rabota", title: "Контрольная работа", kind: "grade"  },
  { segment: "kursovaya-rabota",   title: "Курсовая работа",    kind: "grade"  },
  { segment: "kursovoy-proekt",    title: "Курсовой проект",    kind: "grade"  },
  { segment: "praktika",           title: "Практика",           kind: "grade"  },
];

/** Виды работ внутри контрольной точки — колонки попапа детализации. */
export const WORK_LABELS = {
  lecture: "Лекции",
  practice: "Практика",
  lab: "Лаб. работы",
  other: "Другое",
};

/** Прочерк для пустых значений. */
export const DASH = "—";

/** Ключи localStorage. Префикс общий, чтобы не путаться с чужими записями. */
export const STORAGE_KEYS = {
  zach: "rating:lastZach",
  theme: "rating:theme",
};
