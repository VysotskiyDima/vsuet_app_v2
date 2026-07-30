/**
 * Моковое расписание — заглушка до появления настоящего источника.
 *
 * Пока одно и то же для числителя и знаменателя и для всех пользователей.
 * Когда появится API, этот файл заменяется загрузчиком с той же формой данных:
 * { time, name, type, room, teacher, subgroup }.
 */

export const SCHED_DAYS = ["ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА"];
export const SCHED_DOW_SHORT = { "ПОНЕДЕЛЬНИК": "Пн", "ВТОРНИК": "Вт", "СРЕДА": "Ср", "ЧЕТВЕРГ": "Чт", "ПЯТНИЦА": "Пт", "СУББОТА": "Сб" };
export const LESSON_TYPES = { lecture: "Лекция", practice: "Практика", lab: "Лаб. работа", seminar: "Семинар" };

export const MOCK_GROUP = "ПИ-231";
export const MOCK_SCHEDULE = {
  "ПОНЕДЕЛЬНИК": [
    { time: "08.00-09.35", name: "Математический анализ",       type: "lecture",  room: "К-301", teacher: "Иванова Т. С.", subgroup: "" },
    { time: "09.45-11.20", name: "Программирование на Python",  type: "lab",      room: "А-215", teacher: "Петров А. В.", subgroup: "1" },
    { time: "11.50-13.25", name: "Дискретная математика",       type: "practice", room: "К-118", teacher: "Сидорова Е. Н.", subgroup: "2" },
  ],
  "ВТОРНИК": [
    { time: "09.45-11.20", name: "Базы данных",                 type: "lecture",  room: "К-204", teacher: "Кузнецов Д. И.", subgroup: "" },
    { time: "11.50-13.25", name: "Базы данных",                 type: "lab",      room: "А-217", teacher: "Кузнецов Д. И.", subgroup: "1" },
    { time: "13.35-15.10", name: "Иностранный язык",            type: "seminar",  room: "Г-402", teacher: "Морозова И. П.", subgroup: "" },
  ],
  "СРЕДА": [
    { time: "08.00-09.35", name: "Операционные системы",        type: "lecture",  room: "К-301", teacher: "Фёдоров С. А.", subgroup: "" },
    { time: "09.45-11.20", name: "Операционные системы",        type: "practice", room: "А-215", teacher: "Фёдоров С. А.", subgroup: "2" },
    { time: "11.50-13.25", name: "Физическая культура",         type: "practice", room: "Спорткомплекс", teacher: "", subgroup: "1" },
    { time: "13.35-15.10", name: "Философия",                   type: "lecture",  room: "Г-210", teacher: "Волкова Н. М.", subgroup: "" },
  ],
  "ЧЕТВЕРГ": [
    { time: "09.45-11.20", name: "Веб-технологии",              type: "lab",      room: "А-219", teacher: "Николаев П. Р.", subgroup: "2" },
    { time: "11.50-13.25", name: "Компьютерные сети",           type: "lecture",  room: "К-204", teacher: "Егоров В. Л.", subgroup: "" },
  ],
  "ПЯТНИЦА": [
    { time: "08.00-09.35", name: "Теория вероятностей",         type: "lecture",  room: "К-301", teacher: "Иванова Т. С.", subgroup: "" },
    { time: "09.45-11.20", name: "Теория вероятностей",         type: "practice", room: "К-118", teacher: "Иванова Т. С.", subgroup: "1" },
    { time: "11.50-13.25", name: "Программная инженерия",       type: "seminar",  room: "А-215", teacher: "Петров А. В.", subgroup: "" },
  ],
  "СУББОТА": [
    { time: "09.45-11.20", name: "Архитектура ЭВМ",             type: "lecture",  room: "К-204", teacher: "Егоров В. Л.", subgroup: "" },
    { time: "11.50-13.25", name: "Веб-технологии",              type: "practice", room: "А-219", teacher: "Николаев П. Р.", subgroup: "2" },
  ],
};
