from __future__ import annotations

import customtkinter as ctk

from creator_desktop.facts_review import show_json_dialog
from models import DirectorOutput


class DirectorReviewFrame(ctk.CTkFrame):
    def __init__(self, master, output: DirectorOutput, on_verify, on_back, on_retry) -> None:
        super().__init__(master)
        self.output, self._on_verify = output, on_verify
        ctk.CTkLabel(self, text="确认导演方案摘要", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=20, pady=(18, 4), anchor="w")
        ctk.CTkLabel(self, text="请确认方案忠实反映你的原文。若需修改，请返回调整导演方案原文后重新解析。", wraplength=850, justify="left").pack(padx=20, pady=(0, 8), anchor="w")
        body = ctk.CTkScrollableFrame(self, label_text=f"镜头数量：{len(output.shots)}")
        body.pack(fill="both", expand=True, padx=20, pady=8)
        for shot in output.shots:
            card = ctk.CTkFrame(body)
            card.pack(fill="x", padx=6, pady=6)
            ctk.CTkLabel(card, text=f"{shot.shot_id}｜{shot.start_time}-{shot.end_time}秒", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=(7, 2), anchor="w")
            for label, value in (("开场状态", shot.opening_state), ("动作路径", shot.action_path), ("结尾状态", shot.ending_state), ("台词", "；".join(f"{x.speaker}：{x.text}" for x in shot.dialogue)), ("负面约束", "；".join(shot.negative_constraints))):
                if value:
                    ctk.CTkLabel(card, text=f"{label}：{value}", justify="left", wraplength=820, anchor="w").pack(fill="x", padx=10, pady=2)
        self.semantic = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="同时执行DeepSeek语义审计", variable=self.semantic).pack(padx=20, pady=4, anchor="w")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=12)
        ctk.CTkButton(buttons, text="开始核验", command=lambda: on_verify(self.semantic.get())).pack(side="left")
        ctk.CTkButton(buttons, text="返回修改导演原文", command=on_back).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="重新解析", command=on_retry).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="查看专业JSON", command=lambda: show_json_dialog(self, output)).pack(side="right")
