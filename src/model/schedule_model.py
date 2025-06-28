from typing import List, Dict, Any

class ScheduleModel:
    """
    日程表数据结构与操作
    """
    def __init__(self, schedules: List[Dict[str, Any]] = None):
        self.schedules = schedules or []

    def add_schedule(self, schedule: Dict[str, Any]):
        self.schedules.append(schedule)

    def remove_schedule(self, idx: int):
        if 0 <= idx < len(self.schedules):
            self.schedules.pop(idx)

    def get_all(self) -> List[Dict[str, Any]]:
        return self.schedules

    def get_today(self, today: str) -> List[Dict[str, Any]]:
        return [s for s in self.schedules if s.get('date') == today]
