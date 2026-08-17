#
# Copyright (c) 2022-2026 Antmicro
#
# This file is licensed under the Apache License.
# Full license text is available in 'LICENSE'.
#

from rich.prompt import PromptBase, InvalidResponse

class RemoveInstancesPrompt(PromptBase):
    response_type = list

    REMOVE_NOTHING_OPTION = "N"
    REMOVE_ALL_OPTION = "a"

    default = REMOVE_NOTHING_OPTION
    case_sensitive = False

    def __init__(self, packages_to_remove: list, *args, **kwargs):
        self.packages_to_remove = packages_to_remove
        self.max_val = len(packages_to_remove)

        prompt_text = f'Enter number of the instance to remove: (e.g. "1 2", "3-5", "^4-6") or ({self.REMOVE_NOTHING_OPTION}=neither, {self.REMOVE_ALL_OPTION}=remove all)\n'
        super().__init__(prompt_text, *args, **kwargs)

    def pre_prompt(self):
        print("Found multiple instances of given version:")
        package_id = 1
        for package_path in self.packages_to_remove:
            print(f"{package_id}. {str(package_path)}")
            package_id += 1

    def process_response(self, value: str):
        response_str = value.strip()

        if response_str.lower() == self.REMOVE_NOTHING_OPTION.lower():
            return []
        elif response_str.lower() == self.REMOVE_ALL_OPTION.lower():
            return list(range(1, self.max_val + 1))

        selected_indices = self.parse_range_selection(response_str, self.max_val)
        return [self.packages_to_remove[i - 1] for i in selected_indices]

    # Parses space-separated numbers, ranges, and mixed selections (e.g., '1 3-5 7') into a sorted list of unique indices within the valid range
    @staticmethod
    def parse_range_selection(selection_str: str, max_val: int) -> list[int]:
        selected_indices = set()
        excluded_indices = set()
        parts = selection_str.split()

        try:
            for part in parts:
                indices = selected_indices
                if part.startswith('^'):
                    indices = excluded_indices
                    part = part[1:]

                if '-' in part:
                    start_str, end_str = part.split('-', 1)
                    start, end = int(start_str), int(end_str)

                    range_start = max(1, start)
                    range_end = min(max_val, end)

                    indices.update(range(range_start, range_end + 1))
                else:
                    i = int(part)
                    if 1 <= i <= max_val:
                        indices.add(i)
                    else:
                        raise ValueError(f"Index {i} out of range")

        except(ValueError) as e:
            raise InvalidResponse(f"Invalid selection format: {e}. Please enter numbers or ranges (e.g. 1 3-5)")
        
        if excluded_indices:
            selected_indices = excluded_indices.symmetric_difference(range(1, max_val + 1))
                    
        return sorted(list(selected_indices))

