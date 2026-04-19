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
                min_percent_threshold (float): порог в процентах от среднего (по умолчанию 5).
                smoothing_window (int): размер окна для сглаживания (0 - отключено,
                                          положительное число - количество значимых интервалов
                                          слева и справа от текущего, которые учитываются)
                font_size (int): размер шрифта для всех текстовых элементов графика (по умолчанию 12).
        """
        self.prefs = preferences
        self.data_file = preferences.get('data_file', 'agent_data/analysis_step_3.json')
        self.log_level = preferences.get('log_level', 2)
        self.threshold_percent = preferences.get('min_percent_threshold', 5.0)
        self.smoothing_window = preferences.get('smoothing_window', 0)
        self.font_size = preferences.get('font_size', 12)  # размер шрифта из конфига
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
        if self.log_level >= level:
            print(*args, **kwargs)

    def run(self):
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
        self._log(1, "\n" + "=" * 100)
        self._log(1, "🚀 ПОСТРОЕНИЕ ГРАФИКА")
        self._log(1, "=" * 100)
        self._log(1, f"📌 interval_days = {interval_days}")
        self._log(1, f"📌 Порог: {self.threshold_percent}% от среднего")
        self._log(1, f"📌 Окно сглаживания: {self.smoothing_window}")
        self._log(1, f"📌 Размер шрифта: {self.font_size}")

        # Устанавливаем глобальный размер шрифта для всех элементов графика
        plt.rcParams.update({'font.size': self.font_size})

        # Границы
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59) if end_date else None

        # Сбор дат по категориям (исключаем группу "Не классифицировано")
        categories_data = {}
        excluded_count = 0
        for cat in self.data:
            name = cat.get('name', 'Без названия')
            # Пропускаем категорию с названием "Не классифицировано"
            if "Не классифицировано" in name:
                excluded_count += 1
                continue
            dates = []
            for p in cat.get('participants', []):
                dt = self._parse_date(p.get('date'))
                if dt and (not start_dt or dt >= start_dt) and (not end_dt or dt <= end_dt):
                    dates.append(dt)
            if dates:
                categories_data[name] = sorted(dates)

        if excluded_count:
            self._log(1, f"⚠️ Исключено {excluded_count} категорий с названием 'Не классифицировано'")

        if not categories_data:
            self._log(1, "❌ НЕТ ДАННЫХ ПОСЛЕ ИСКЛЮЧЕНИЯ НЕКЛАССИФИЦИРОВАННЫХ КАТЕГОРИЙ!")
            return

        # Глобальный диапазон
        all_dates = [d for dates in categories_data.values() for d in dates]
        global_min = min(all_dates).replace(hour=0, minute=0, second=0, microsecond=0)
        global_max = max(all_dates)

        start_dt = start_dt or global_min
        end_dt = end_dt or global_max

        # Формируем интервалы
        intervals = []
        cur = start_dt
        while cur <= end_dt:
            nxt = cur + timedelta(days=interval_days)
            intervals.append((cur, nxt))
            cur = nxt
        total_intervals = len(intervals)
        self._log(1, f"📊 Всего интервалов: {total_intervals}")

        # Подсчёт сырых значений по интервалам
        raw = {cat: [0]*total_intervals for cat in categories_data}
        last_vote = {cat: {} for cat in categories_data}
        for cat, dates in categories_data.items():
            for idx, (int_start, int_end) in enumerate(intervals):
                cnt = sum(1 for d in dates if int_start <= d < int_end)
                raw[cat][idx] = cnt
                if cnt:
                    last_vote[cat][idx] = max(d for d in dates if int_start <= d < int_end)

        # Достройка последнего неполного интервала для каждой категории
        for cat in categories_data:
            nonzero = [i for i, v in enumerate(raw[cat]) if v > 0]
            if not nonzero:
                continue
            last_idx = nonzero[-1]
            int_start, int_end = intervals[last_idx]
            has_after = any(d >= int_end for d in categories_data[cat])
            if not has_after and last_idx in last_vote[cat]:
                last = last_vote[cat][last_idx]
                interval_len = (int_end - int_start).total_seconds()
                covered = (last - int_start).total_seconds()
                if covered > 0:
                    raw[cat][last_idx] = round(raw[cat][last_idx] * (interval_len / covered))

        # ========== ПРИМЕНЕНИЕ ПОРОГА (отсечение незначащих интервалов) ==========
        threshold = {}
        filtered = {}
        for cat in categories_data:
            vals = raw[cat]
            # Среднее по всем интервалам (включая нулевые)
            mean_val = sum(vals) / total_intervals if total_intervals else 0
            thr = mean_val * (self.threshold_percent / 100.0)
            threshold[cat] = thr
            # Обнуляем значения ниже порога
            filtered[cat] = [v if v >= thr else 0 for v in vals]

        # ========== СГЛАЖИВАНИЕ по значимым (ненулевым) интервалам ==========
        if self.smoothing_window > 0:
            w = self.smoothing_window
            for cat in categories_data:
                vals = filtered[cat]
                # Находим индексы значимых интервалов (после порога они ненулевые)
                sig_indices = [i for i, v in enumerate(vals) if v > 0]
                if not sig_indices:
                    continue
                smoothed_vals = vals[:]  # копия
                for pos, idx in enumerate(sig_indices):
                    left = max(0, pos - w)
                    right = min(len(sig_indices)-1, pos + w)
                    window_indices = sig_indices[left:right+1]
                    window_values = [vals[i] for i in window_indices]
                    smoothed_vals[idx] = sum(window_values) / len(window_values)
                filtered[cat] = smoothed_vals
            self._log(1, f"   ✅ Сглаживание применено (симметричное окно {w} по значимым интервалам)")

        # ========== ПОДГОТОВКА ДАННЫХ ДЛЯ ГРАФИКА ==========
        # Оставляем только точки со значением > 0
        plot_data = {}  # cat -> list of (date, value)
        for cat in categories_data:
            points = []
            for idx, val in enumerate(filtered[cat]):
                if val > 0:
                    points.append((intervals[idx][0], val))
            if points:
                plot_data[cat] = points
            else:
                self._log(2, f"   {cat}: нет точек после фильтрации")

       # ========== ПОСТРОЕНИЕ ГРАФИКА ==========
        fig, ax = plt.subplots(figsize=(14, 7))
        for cat, points in plot_data.items():
            if not points:
                continue
            dates, values = zip(*points)
            ax.plot(dates, values, marker='o', linestyle='-', label=cat, markersize=6, linewidth=2)

        ax.set_xlabel('Дата')
        ax.set_ylabel('Количество голосов')
        ax.set_title(f'Динамика голосов (интервал {interval_days} дн.)')
        ax.grid(True, linestyle='--', alpha=0.7)
        plt.xticks(rotation=45)

        # --- Динамический расчёт параметров легенды ---
        num_cats = len(plot_data)
        if num_cats == 0:
            self._log(1, "⚠️ Нет категорий для отображения легенды")
            return

        # Базовые значения для N=2, F=20
        base_offset = -0.30
        base_bottom = 0.15   # стандартный нижний отступ

        # Масштабируем пропорционально количеству категорий и размеру шрифта
        scale_factor = (num_cats / 2.0) * (self.font_size / 20.0)
        y_offset = base_offset * scale_factor
        bottom_margin = base_bottom * scale_factor

        # Ограничиваем сверху, чтобы легенда не ушла слишком далеко
        y_offset = max(-0.8, min(-0.1, y_offset))   # от -0.1 до -0.8
        bottom_margin = min(0.5, max(0.1, bottom_margin))  # от 0.1 до 0.5

        self._log(2, f"📐 Легенда: категорий={num_cats}, шрифт={self.font_size}, "
                     f"y_offset={y_offset:.3f}, bottom={bottom_margin:.3f}")

        # Размещение легенды
        ax.legend(
            loc='upper center',
            bbox_to_anchor=(0.5, y_offset),
            fontsize=self.font_size,
            ncol=1,
            frameon=False
        )

        # Корректировка нижнего отступа
        plt.subplots_adjust(bottom=bottom_margin)

        # Сохранение и показ
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self._log(1, f"✅ График сохранён: {save_path}")
        if show:
            plt.show()
        else:
            plt.close()
        self._log(1, "✅ ЗАВЕРШЕНО")
