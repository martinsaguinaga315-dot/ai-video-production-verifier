from __future__ import annotations

import customtkinter as ctk

from models import VerificationReport


class CreatorResultFrame(ctk.CTkFrame):
    def __init__(self, master, report: VerificationReport, on_export_report, on_export_facts, on_export_output, on_restart) -> None:
        super().__init__(master)
        ctk.CTkLabel(self, text="核验结果", font=ctk.CTkFont(size=22, weight="bold")).pack(padx=20, pady=(18, 6), anchor="w")
        ctk.CTkLabel(self, text=f"{'通过' if report.passed else '未通过'}｜分数 {report.score}｜错误 {report.errors}｜警告 {report.warnings}", font=ctk.CTkFont(size=16, weight="bold")).pack(padx=20, pady=4, anchor="w")
        body = ctk.CTkScrollableFrame(self, label_text="问题列表")
        body.pack(fill="both", expand=True, padx=20, pady=8)
        if not report.issues:
            ctk.CTkLabel(body, text="未发现问题。", font=ctk.CTkFont(size=16)).pack(pady=24)
        for issue in report.issues:
            ctk.CTkLabel(body, text=f"{issue.severity.upper()}｜{issue.rule_id}｜{issue.title}\n{issue.message}\n{issue.suggestion}", justify="left", wraplength=830, anchor="w").pack(fill="x", padx=8, pady=7)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=12)
        ctk.CTkButton(buttons, text="导出核验报告.json", command=on_export_report).pack(side="left")
        ctk.CTkButton(buttons, text="导出facts.json", command=on_export_facts).pack(side="left", padx=7)
        ctk.CTkButton(buttons, text="导出director_output.json", command=on_export_output).pack(side="left", padx=7)
        ctk.CTkButton(buttons, text="返回普通创作者模式", command=on_restart).pack(side="right")
