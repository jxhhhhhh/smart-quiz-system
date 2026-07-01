#!/usr/bin/env python3
"""
Smart Quiz System - Main Entry (CLI)
支持五种题型：单选 / 多选 / 判断 / 填空 / 简答
"""

import sys
import os
import json
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from question_importer import QuestionBankImporter
from practice_session import PracticeSession, QuestionPractice
from parser import check_answer


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def import_questions_flow():
    print("\n--- 导入题目 ---")
    print("1. 粘贴文本内容")
    print("2. 从文件导入 (questions.txt)")
    choice = input("选择来源 (1-2): ").strip()

    content = ""
    if choice == '1':
        print("粘贴题目内容（连续两次回车结束）：")
        lines = []
        empty_count = 0
        while True:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
            else:
                empty_count = 0
                lines.append(line)
        content = "\n".join(lines)
    elif choice == '2':
        filepath = input("输入文件路径: ").strip()
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            print(f"错误：文件 {filepath} 不存在。")
            return

    if content:
        subject = input("学科分类（如 Python，可留空）: ").strip()
        importer = QuestionBankImporter()
        count, errors, report = importer.import_from_text(content, subject=subject)
        importer.close()
        print(f"\n{'='*40}")
        print(f"导入完成！")
        print(f"  成功导入：{count} 题")
        print(f"  重复跳过：{report.get('skipped_dup', 0)} 题")
        print(f"  质量跳过：{report.get('skipped_quality', 0)} 题")
        print(f"  导入失败：{report.get('failed', 0)} 题")
        if errors:
            for e in errors:
                print(f"  ⚠️ {e}")


def _display_question(q, index, total):
    """显示题目内容和选项，返回用户答案。"""
    q_type = q.get('question_type', 'single')
    type_names = {
        'single': '单选题', 'multi': '多选题', 'judge': '判断题',
        'fill': '填空题', 'short': '简答题'
    }
    type_label = type_names.get(q_type, q_type)

    print(f"\n{'─'*50}")
    print(f"[{index}/{total}] 【{type_label}】{q['question_content']}")

    options = q.get('options', {})
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except (json.JSONDecodeError, TypeError):
            options = {}

    if options:
        for k, v in options.items():
            print(f"  {k}. {v}")

    # 根据题型提示输入方式
    if q_type == 'multi':
        hint = "输入答案（如 ABD，多选）: "
    elif q_type == 'judge':
        hint = "输入答案（A=正确, B=错误）: "
    elif q_type in ('fill', 'short'):
        hint = "输入答案: "
    else:
        hint = "输入答案（如 A）: "

    answer = input(hint).strip()
    return answer


def practice_flow():
    print("\n--- 开始练习 ---")
    print("1. 随机模式")
    print("2. 错题重练")
    print("3. 难度专项")
    mode_choice = input("选择模式 (1-3): ").strip()

    mode_map = {'1': 'random', '2': 'wrong', '3': 'difficulty'}
    mode = mode_map.get(mode_choice, 'random')

    difficulty = None
    if mode == 'difficulty':
        diff_input = input("难度 (1=简单, 2=中等, 3=困难): ").strip()
        if diff_input in ['1', '2', '3']:
            difficulty = int(diff_input)
        else:
            print("无效难度，默认为 1。")
            difficulty = 1

    count = 5
    try:
        count = int(input("题目数量（默认 5）: ").strip())
    except ValueError:
        pass

    session = PracticeSession()
    questions = session.get_questions(mode, count, difficulty)
    session.close()

    if not questions:
        print("没有找到符合条件的题目。")
        return

    practice = QuestionPractice()
    correct = 0

    for i, q in enumerate(questions):
        question_start = time.time()
        answer = _display_question(q, i + 1, len(questions))
        time_spent = time.time() - question_start

        q_type = q.get('question_type', 'single')

        # 使用统一答案判断
        is_correct = check_answer(answer, q['correct_answer'], q_type)

        # 记录答题
        practice.check_answer(q['id'], answer, time_spent)

        if is_correct:
            print("✅ 正确！")
            correct += 1
        else:
            print(f"❌ 错误！正确答案：{q['correct_answer']}")

    practice.close()
    accuracy = correct / len(questions) * 100 if questions else 0
    print(f"\n{'='*50}")
    print(f"练习完成！得分：{correct}/{len(questions)}（{accuracy:.0f}%）")
    if accuracy >= 90:
        print("🌟 太棒了！正确率超过 90%！")
    elif accuracy >= 70:
        print("👍 不错！继续保持！")
    elif accuracy >= 50:
        print("💪 还需努力，加油！")
    else:
        print("📚 建议多复习错题！")


def main():
    while True:
        clear_screen()
        print("╔══════════════════════════════════════╗")
        print("║       📚 智能刷题系统 CLI            ║")
        print("╠══════════════════════════════════════╣")
        print("║  1. 导入题目                         ║")
        print("║  2. 开始练习                         ║")
        print("║  3. 启动 Web 界面                    ║")
        print("║  0. 退出                             ║")
        print("╚══════════════════════════════════════╝")

        choice = input("\n请选择: ").strip()

        if choice == '1':
            import_questions_flow()
        elif choice == '2':
            practice_flow()
        elif choice == '3':
            print("\n启动 Web 界面...")
            print("请运行: streamlit run web_interface.py")
            break
        elif choice == '0':
            print("再见！")
            break
        else:
            print("无效选择，请重试。")

        input("\n按回车返回菜单...")


if __name__ == "__main__":
    main()
