import json
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
from typing import List, Dict, Any, Optional


class Visualizer:
    def __init__(self, preferences: dict):
        """
        :param preferences: словарь с настройками визуализатора.
            Ожидаемые ключи:
                data_file (str): путь к JSON-файлу с данными.
                log_level (int): уровень логирования (0-2).
                interval_days (int): размер интервала в днях.
                start_date (str, optional): начальная дата в формате YYYY-MM-DD.
                end_date (str, optional): конечная дата в формате YYYY-MM-DD.
                save_path (str, optional): путь для сохранения графика.
                show (bool): показывать ли график интерактивно.
        """
        self.prefs = preferences
        self.data_file = preferences.get('data_file', 'agent_data/analysis_step_3.json')
        self.log_level = preferences.get('log_level', 2)
        self.data = self._load_data()
        self._log(1, f"✅ Загружено {len(self.data)} категорий из файла {self.data_file}")

    def _load_data(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.data_file):
            raise FileNotFoundError(f"Файл {self.data_file} не найден.")
        with open(self.data_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        formats = [
            "%H:%M %d.%m.%Y",
            "%d.%m.%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%d.%m.%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _log(self, level: int, *args, **kwargs):
        """Выводит сообщение, если текущий уровень логирования >= level."""
        if self.log_level >= level:
            print(*args, **kwargs)

    def run(self):
        """Запускает построение графика с параметрами из preferences."""
        self.plot_votes_over_intervals(
            interval_days=self.prefs.get('interval_days', 7),
            start_date=self.prefs.get('start_date'),
            end_date=self.prefs.get('end_date'),
            save_path=self.prefs.get('save_path'),
            show=self.prefs.get('show', False)
        )

    def plot_votes_over_intervals(self, interval_days: int, start_date: Optional[str] = None,
                                   end_date: Optional[str] = None, save_path: Optional[str] = None,
                                   show: bool = True):
        """
        Интервал считается заполненным, если есть хотя бы один голос после его окончания.
        Если последний интервал с данными не заполнен (нет голосов после него),
        он достраивается пропорционально фактической длине охвата внутри этого интервала.
        """
        self._log(1, "\n" + "=" * 100)
        self._log(1, "🚀 НАЧАЛО ПОСТРОЕНИЯ ГРАФИКА")
        self._log(1, "=" * 100)
        self._log(1, f"📌 Параметр interval_days = {interval_days} дн.")
        
        # ========== ШАГ 1: Обработка входных дат ==========
        self._log(1, "\n" + "=" * 100)
        self._log(1, "📅 ШАГ 1: ОБРАБОТКА ВХОДНЫХ ДАТ")
        self._log(1, "=" * 100)
        
        start_dt = None
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            self._log(2, f"   start_date задан: {start_date} → {start_dt}")
        else:
            self._log(2, "   start_date НЕ задан")
        
        end_dt = None
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            self._log(2, f"   end_date задан: {end_date} → {end_dt}")
        else:
            self._log(2, "   end_date НЕ задан")

        # ========== ШАГ 2: Сбор дат по категориям ==========
        self._log(1, "\n" + "=" * 100)
        self._log(1, "📂 ШАГ 2: СБОР ДАТ ПО КАТЕГОРИЯМ")
        self._log(1, "=" * 100)
        
        categories_data = {}
        categories_last_date = {}
        
        for cat_idx, category in enumerate(self.data):
            name = category.get('name', 'Без названия')
            participants = category.get('participants', [])
            self._log(2, f"\n   📁 Категория {cat_idx + 1}/{len(self.data)}: '{name}'")
            
            dates = []
            for p in participants:
                date_str = p.get('date')
                if not date_str:
                    continue
                dt = self._parse_date(date_str)
                if dt is None:
                    continue
                if start_dt and dt < start_dt:
                    continue
                if end_dt and dt > end_dt:
                    continue
                dates.append(dt)
            
            if dates:
                categories_data[name] = sorted(dates)
                categories_last_date[name] = max(dates)
                self._log(2, f"      ✅ Дат после фильтрации: {len(dates)}")
                self._log(2, f"      📍 Диапазон: {min(dates).strftime('%d.%m %H:%M')} — {max(dates).strftime('%d.%m %H:%M')}")
            else:
                self._log(2, f"      ⚠️ Нет данных после фильтрации")

        self._log(1, f"\n   📊 ВСЕГО категорий с данными: {len(categories_data)}")
        total_votes = sum(len(dates) for dates in categories_data.values())
        self._log(1, f"   📊 ВСЕГО голосов: {total_votes}")

        if not categories_data:
            self._log(1, "❌ НЕТ ДАННЫХ!")
            return

        # ========== ШАГ 3: Глобальный диапазон ==========
        self._log(1, "\n" + "=" * 100)
        self._log(1, "🌍 ШАГ 3: ГЛОБАЛЬНЫЙ ДИАПАЗОН ДАТ")
        self._log(1, "=" * 100)
        
        all_dates = []
        for dates in categories_data.values():
            all_dates.extend(dates)
        
        global_min = min(all_dates)
        global_max = max(all_dates)
        
        self._log(2, f"   Глобальный минимум: {global_min.strftime('%d.%m.%Y %H:%M:%S')}")
        self._log(2, f"   Глобальный максимум: {global_max.strftime('%d.%m.%Y %H:%M:%S')}")

        if start_dt is None:
            start_dt = global_min.replace(hour=0, minute=0, second=0, microsecond=0)
            self._log(2, f"   ✅ start_dt = {start_dt}")
        
        if end_dt is None:
            end_dt = global_max
            self._log(2, f"   ✅ end_dt = {end_dt}")

        # ========== ШАГ 4: Создание интервалов ==========
        self._log(1, "\n" + "=" * 100)
        self._log(1, "📏 ШАГ 4: СОЗДАНИЕ ИНТЕРВАЛОВ")
        self._log(1, "=" * 100)
        
        intervals = []
        current = start_dt
        interval_num = 0
        
        while current <= end_dt:
            interval_end = current + timedelta(days=interval_days)
            intervals.append((current, interval_end))
            self._log(2, f"   Интервал #{interval_num}: [{current.strftime('%d.%m')} — {interval_end.strftime('%d.%m')}]")
            current = interval_end
            interval_num += 1
        
        self._log(1, f"   ✅ ВСЕГО интервалов: {len(intervals)}")

        # ========== ШАГ 5: Подсчёт голосов и определение заполненности ==========
        self._log(1, "\n" + "=" * 100)
        self._log(1, "📊 ШАГ 5: ПОДСЧЁТ ГОЛОСОВ ПО ИНТЕРВАЛАМ")
        self._log(1, "=" * 100)
        
        category_interval_counts = {}      # {cat_name: {idx: count}}
        category_interval_filled = {}      # {cat_name: {idx: bool}}
        category_last_vote_in_interval = {} # для достройки: {cat_name: {idx: datetime}}
        
        for cat_name, dates in categories_data.items():
            # Для уровня 1 выводим краткую информацию о категории
            self._log(1, f"\n   📁 {cat_name}")
            
            # Для уровня 2 выводим детали
            self._log(2, f"\n{'=' * 80}")
            self._log(2, f"   КАТЕГОРИЯ: '{cat_name}'")
            self._log(2, f"{'=' * 80}")
            self._log(2, f"   Всего голосов: {len(dates)}")
            self._log(2, f"   Последняя дата: {categories_last_date[cat_name].strftime('%d.%m.%Y %H:%M:%S')}")
            
            category_interval_counts[cat_name] = {}
            category_interval_filled[cat_name] = {}
            category_last_vote_in_interval[cat_name] = {}
            
            intervals_with_data = 0
            for idx, (int_start, int_end) in enumerate(intervals):
                # голоса в интервале [int_start, int_end)
                votes_in_interval = [d for d in dates if int_start <= d < int_end]
                count = len(votes_in_interval)
                category_interval_counts[cat_name][idx] = count
                
                if count > 0:
                    intervals_with_data += 1
                    category_last_vote_in_interval[cat_name][idx] = max(votes_in_interval)
                
                # заполнен ли интервал? (есть голос после конца)
                has_voice_after = any(d >= int_end for d in dates)
                category_interval_filled[cat_name][idx] = has_voice_after
                
                self._log(2, f"   Интервал #{idx} [{int_start.strftime('%d.%m')}-{int_end.strftime('%d.%m')}]: {count} голосов — {'✅' if has_voice_after else '❌'}")
            
            # Для уровня 1 добавим сводку: общее число голосов и сколько интервалов затронуто
            self._log(1, f"      Всего {len(dates)} голосов, данные в {intervals_with_data} интервалах")

        # ========== ШАГ 6: Достройка последнего неполного интервала ==========
        self._log(1, "\n" + "=" * 100)
        self._log(1, "🔧 ШАГ 6: ДОСТРОЙКА ПОСЛЕДНЕГО НЕПОЛНОГО ИНТЕРВАЛА")
        self._log(1, "=" * 100)
        
        total_intervals = len(intervals)
        self._log(1, f"   Общее количество интервалов: {total_intervals}")
        
        for cat_name, dates in categories_data.items():
            # Для уровня 1 выводим заголовок категории без лишних разделителей
            self._log(1, f"\n   📁 {cat_name}")
            
            # Для уровня 2 оставляем полный вывод
            self._log(2, f"\n{'=' * 80}")
            self._log(2, f"   📁 КАТЕГОРИЯ: '{cat_name}'")
            self._log(2, f"{'=' * 80}")
            
            # 6.1: Поиск последнего интервала с данными
            self._log(2, f"\n   🔍 6.1: ПОИСК ПОСЛЕДНЕГО ИНТЕРВАЛА С ДАННЫМИ")
            
            last_data_idx = -1
            for idx in range(total_intervals - 1, -1, -1):
                count = category_interval_counts[cat_name][idx]
                if count > 0 and last_data_idx == -1:
                    last_data_idx = idx
                    self._log(2, f"      ✅ НАЙДЕН: интервал #{idx} ({count} голосов)")
            
            if last_data_idx == -1:
                self._log(2, f"   ⚠️ Нет данных — пропускаем")
                continue
            
            self._log(2, f"   📌 last_data_idx = {last_data_idx}")
            
            # 6.2: Проверка заполненности последнего интервала с данными
            self._log(2, f"\n   🔍 6.2: ПРОВЕРКА ЗАПОЛНЕННОСТИ")
            
            last_interval_end = intervals[last_data_idx][1]
            voices_after = [d for d in dates if d >= last_interval_end]
            
            self._log(2, f"   Конец интервала {last_data_idx}: {last_interval_end.strftime('%d.%m.%Y %H:%M:%S')}")
            self._log(2, f"   Голосов после конца: {len(voices_after)}")
            
            is_filled = len(voices_after) > 0
            
            # 6.3: Если не заполнен — применяем достройку по времени
            if not is_filled:
                self._log(2, f"\n   🔧 6.3: ПРИМЕНЕНИЕ ДОСТРОЙКИ (по фактической длине охвата)")
                
                last_vote_in_interval = category_last_vote_in_interval[cat_name][last_data_idx]
                int_start, int_end = intervals[last_data_idx]
                
                interval_length_hours = (int_end - int_start).total_seconds() / 3600
                covered_length_hours = (last_vote_in_interval - int_start).total_seconds() / 3600
                
                if covered_length_hours <= 0:
                    self._log(2, f"   ⚠️ Странная ситуация: покрытая длина <= 0, оставляем как есть")
                    multiplier = 1.0
                else:
                    multiplier = interval_length_hours / covered_length_hours
                
                self._log(2, f"   Интервал {last_data_idx}: {int_start.strftime('%d.%m %H:%M')} — {int_end.strftime('%d.%m %H:%M')}")
                self._log(2, f"   Последний голос в интервале: {last_vote_in_interval.strftime('%d.%m %H:%M')}")
                self._log(2, f"   Длина интервала: {interval_length_hours:.2f} ч")
                self._log(2, f"   Охвачено данными: {covered_length_hours:.2f} ч")
                self._log(2, f"   Коэффициент достройки: {multiplier:.4f}")
                
                original_value = category_interval_counts[cat_name][last_data_idx]
                new_value = round(original_value * multiplier)
                
                self._log(2, f"   📊 ДОСТРОЙКА:")
                self._log(2, f"   Интервал #{last_data_idx}: {original_value} × {multiplier:.4f} = {original_value * multiplier:.2f} → {new_value}")
                
                category_interval_counts[cat_name][last_data_idx] = new_value
            else:
                self._log(2, f"\n   ⏭️ ДОСТРОЙКА НЕ ТРЕБУЕТСЯ (интервал заполнен)")
            
            # 6.4: Итоговые значения (выводим компактно для уровня 1, подробно для уровня 2)
            values = [category_interval_counts[cat_name].get(i, 0) for i in range(total_intervals)]
            self._log(1, f"      Итоговые значения: {values}")
            
            if self.log_level >= 2:
                self._log(2, f"\n   📋 6.4: ИТОГОВЫЕ ЗНАЧЕНИЯ:")
                for idx in range(total_intervals):
                    self._log(2, f"   Интервал #{idx}: {values[idx]}")

        # ========== ШАГ 7: Данные для графика ==========
        self._log(1, "\n" + "=" * 100)
        self._log(1, "📈 ШАГ 7: ДАННЫЕ ДЛЯ ГРАФИКА")
        self._log(1, "=" * 100)
        
        x = list(range(len(intervals)))
        all_categories = sorted(categories_data.keys())
        interval_labels = [f"{start.strftime('%d.%m')}-{end.strftime('%d.%m')}" 
                          for start, end in intervals]
        
        self._log(2, f"   Ось X: {x}")
        self._log(2, f"   Подписи: {interval_labels}")
        
        self._log(1, f"\n   ЗНАЧЕНИЯ ПО КАТЕГОРИЯМ:")
        for cat in all_categories:
            y = [category_interval_counts[cat].get(i, 0) for i in x]
            self._log(1, f"   {cat}: {y}")

        # ========== ШАГ 8: Построение ==========
        self._log(1, "\n" + "=" * 100)
        self._log(1, "🎨 ШАГ 8: ПОСТРОЕНИЕ ГРАФИКА")
        self._log(1, "=" * 100)
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        for cat in all_categories:
            y = [category_interval_counts[cat].get(i, 0) for i in x]
            ax.plot(x, y, marker='o', linestyle='-', label=cat, markersize=8, linewidth=2)
            self._log(2, f"   Построено: '{cat}': {y}")

        ax.set_xlabel('Временной интервал', fontsize=12)
        ax.set_ylabel('Количество голосов', fontsize=12)
        ax.set_title(f'Динамика количества голосов (интервал = {interval_days} дн.)', fontsize=14)
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), fontsize=9)
        ax.grid(True, linestyle='--', alpha=0.7)

        ax.set_xticks(x)
        ax.set_xticklabels(interval_labels, rotation=45, ha='right')
        
        for i in range(len(intervals) + 1):
            ax.axvline(x=i-0.5, color='gray', linestyle=':', alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self._log(1, f"\n   ✅ Сохранено: {save_path}")

        if show:
            plt.show()
        else:
            plt.close()
            self._log(2, f"   Окно закрыто (show=False)")
        
        self._log(1, "\n" + "=" * 100)
        self._log(1, "✅ ЗАВЕРШЕНИЕ")
        self._log(1, "=" * 100 + "\n")