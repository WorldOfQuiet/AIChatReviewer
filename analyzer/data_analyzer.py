import time
from typing import Optional
from tqdm import tqdm

from .base_analyzer import BaseAnalyzer
from .step1_analyzer import Step1Analyzer
from .step2_aggregator import Step2Aggregator
from .step3_mapper import Step3Mapper


class DataAnalyzer(Step1Analyzer, Step2Aggregator, Step3Mapper):
    """Многошаговый анализ чатов с использованием LLM."""

    def run(self):
        """Запуск шагов в соответствии с настройками с замером времени."""
        start_time = time.time()
        self._log(1, "Запуск анализатора")
        self._log(1, "=" * 60)

        total_steps = sum([self.step1_enabled, self.step2_enabled, self.step3_enabled])
        main_pbar = tqdm(total=total_steps, desc="Общий прогресс (3 этапа)", position=0) \
                    if self.logging_level == 1 and total_steps > 0 else None

        # Выполнение шагов
        if self.step1_enabled:
            self.step1_analyze_chats(main_pbar)
        else:
            self._log(1, "Шаг 1 отключён в конфигурации")

        if self.step2_enabled:
            self.step2_aggregate_results(main_pbar)
        else:
            self._log(1, "Шаг 2 отключён в конфигурации")

        if self.step3_enabled:
            self.step3_backward_mapping(main_pbar)
        else:
            self._log(1, "Шаг 3 отключён в конфигурации")

        if main_pbar:
            main_pbar.close()

        elapsed = time.time() - start_time
        self._log(1, "=" * 60)
        self._log(1, f"Анализ завершён за {elapsed:.2f} секунд")