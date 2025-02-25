import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

FILE_PROMPT_PATH = "prompts/file-prompt.md"
MATH_PROMPT_PATH = "prompts/math-prompt.md"
ERROR_PROMPT_PATH = "prompts/error.md"

MAX_STEP = 15

load_dotenv(".env.local")

def add_number(val1, val2):
    return float(val1) + float(val2)

def mul_number(val1, val2):
    return float(val1) * float(val2)

def sub_number(val1, val2):
    return float(val1) - float(val2)

def format_tool_result(tool_name, result_value):
    return f"<{tool_name}_result>\n<result>\n{result_value}\n</result>\n</{tool_name}_result>"

def parse_tool_calls(text):
    """
    Parse tool calls from the LLM's output.
    Returns a list of tuples: (tool_name, {parameter_name: parameter_value, ...})
    """
    tool_calls = []
    pattern = r"<(\w+)>(.*?)</\1>"
    matches = re.findall(pattern, text, re.DOTALL)
    for tool_name, inner in matches:
        if tool_name.lower() == "thinking":
            continue
        params = {}
        param_pattern = r"<(\w+)>(.*?)</\1>"
        inner_matches = re.findall(param_pattern, inner, re.DOTALL)
        for p_name, p_val in inner_matches:
            if p_name.lower() == tool_name.lower():
                continue
            params[p_name] = p_val.strip()
        tool_calls.append((tool_name, params))
    return tool_calls

def extract_thinking(text):
    """Extracts and returns the content inside <thinking> tags."""
    thinking_parts = re.findall(r"<thinking>(.*?)</thinking>", text, re.DOTALL)
    return "\n".join(part.strip() for part in thinking_parts)

def main():
    model = ChatOpenAI(model="gpt-4o")
    system_prompt = open(FILE_PROMPT_PATH, "r", encoding="utf-8").read()
    task = "./input.csvにりんごとみかんの値段が書いてあるので、りんご2個とみかん3個を買って、20円クーポンを2枚使用した時の値段を計算して、./output.csvに結果'計算結果'というカラムで保存してください。またこの一連の作業を達成するPythonコードを./accounting.pyに記述してください。最後に全てのタスクが完了したかモデルをo1に切り替えてから確認して回答してください"
    #task = "(12 + 9) * 10 - (3 + 5) * 2"
    user_prompt = f"<task>\n{task}\n</task>"
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    file = open("output.md", "w", encoding="utf-8")
    file.close()
    file = open("output.md", "a", encoding="utf-8")
    file.write(f"""**User**\n\n{user_prompt}\n\n---\n\n""")

    model_mode = "file-io"
    step = 0
    while True:
        result = model.invoke(messages)
        response = result.content
        step += 1
        print(f"\n\nStep: {step}")

        file.write(f"""**Assistant**\n\n{response}\n\n---\n\n""")
        
        thinking_content = extract_thinking(response)
        if thinking_content:
            print(thinking_content)
        try:
            tool_calls = parse_tool_calls(response)
        except Exception as e:
            error_message = open(ERROR_PROMPT_PATH, "r", encoding="utf-8").read()
            messages.append(HumanMessage(content=error_message))
            file.write(f"""**User**\n\n{error_message}\n\n---\n\n""")
            print(f"\nTool Parse Error: {e} \n")
            continue

        if not tool_calls:
            print("No tool calls found in the response.")
            error_message = open(ERROR_PROMPT_PATH, "r", encoding="utf-8").read()
            messages.append(HumanMessage(content=error_message))
            file.write(f"""**User**\n\n{error_message}\n\n---\n\n""")

        finished = False
        for tool_name, params in tool_calls:
            if model_mode == "file-io":
                match tool_name:
                    case "read_file":
                        file_path = params.get("path")
                        file_content = open(file_path, "r", encoding="utf-8").read()
                        print(f"\nファイル読み込み: {file_path}")
                        print(f"ファイル内容: {file_content}\n")
                        tool_result_xml = format_tool_result("read_file", file_content)
                        messages.append(HumanMessage(content=tool_result_xml))
                        file.write(f"""**User**\n\n{tool_result_xml}\n\n---\n\n""")
                    case "write_file":
                        file_path = params.get("path")
                        file_content = params.get("content")
                        open(file_path, "w", encoding="utf-8").write(file_content)
                        print(f"\nファイル書き込み: {file_path}")
                        print(f"ファイル内容: {file_content}\n")
                        tool_result_xml = format_tool_result("write_file", "success")
                        messages.append(HumanMessage(content=tool_result_xml))
                        file.write(f"""**User**\n\n{tool_result_xml}\n\n---\n\n""")
                    case "change_prompt":
                        model_mode = "math"
                        system_prompt = open(MATH_PROMPT_PATH, "r", encoding="utf-8").read()
                        messages.extend([
                            SystemMessage(content=system_prompt),
                            HumanMessage(content="システムプロンプトを切り替えました、回答を続けてください"),
                        ])
                        file.write(f"""**User**\n\nシステムプロンプトを切り替えました、回答を続けてください\n\n---\n\n""")
                        print(f"\n{model_mode}への切り替え\n")
                    case "change_model":
                        model_name = params.get("model_name")
                        model = ChatOpenAI(model=model_name)
                        print(f"\nモデル変更: {model_name}")
                        print(f"現在使用モデル: {model.model_name}\n")
                        tool_result_xml = format_tool_result("change_model", model_name)
                        messages.append(HumanMessage(content=tool_result_xml))
                        file.write(f"""**User**\n\n{tool_result_xml}\n\n---\n\n""")
                    case "attempt_completion":
                        final_result = params.get("result")
                        print("\n最終回答:", final_result, "\n")
                        finished = True
                        break
                    case _:
                        error_message = open(ERROR_PROMPT_PATH, "r", encoding="utf-8").read()
                        messages.append(HumanMessage(content=error_message))
                        file.write(f"""**User**\n\n{error_message}\n\n---\n\n""")
                        print(f"\nUnknown tool: {tool_name} \n")
            elif model_mode == "math":
                match tool_name:
                    case "add_number":
                        val1 = params.get("val1")
                        val2 = params.get("val2")
                        computed = add_number(val1, val2)
                        print(f"\n足し算結果: {val1} + {val2} = {computed}\n")
                        tool_result_xml = format_tool_result("add_number", computed)
                        messages.append(HumanMessage(content=tool_result_xml))
                        file.write(f"""**User**\n\n{tool_result_xml}\n\n---\n\n""")
                    case "sub_number":
                        val1 = params.get("val1")
                        val2 = params.get("val2")
                        computed = sub_number(val1, val2)
                        print(f"\n引き算結果: {val1} - {val2} = {computed}\n")
                        tool_result_xml = format_tool_result("sub_number", computed)
                        messages.append(HumanMessage(content=tool_result_xml))
                        file.write(f"""**User**\n\n{tool_result_xml}\n\n---\n\n""")
                    case "mul_number":
                        val1 = params.get("val1")
                        val2 = params.get("val2")
                        computed = mul_number(val1, val2)
                        print(f"\n掛け算結果: {val1} * {val2} = {computed}\n")
                        tool_result_xml = format_tool_result("mul_number", computed)
                        messages.append(HumanMessage(content=tool_result_xml))
                        file.write(f"""**User**\n\n{tool_result_xml}\n\n---\n\n""")
                    case "change_prompt":
                        model_mode = "file-io"
                        system_prompt = open(FILE_PROMPT_PATH, "r", encoding="utf-8").read()
                        messages.extend([
                            SystemMessage(content=system_prompt),
                            HumanMessage(content="システムプロンプトを切り替えました、回答を続けてください"),
                        ])
                        file.write(f"""**User**\n\nシステムプロンプトを切り替えました、回答を続けてください\n\n---\n\n""")
                        print(f"\n{model_mode}への切り替え\n")
                    case "attempt_completion":
                        final_result = params.get("result")
                        print("\n最終回答:", final_result, "\n")
                        finished = True
                        break
                    case _:
                        error_message = open(ERROR_PROMPT_PATH, "r", encoding="utf-8").read()
                        messages.append(HumanMessage(content=error_message))
                        file.write(f"""**User**\n\n{error_message}\n\n---\n\n""")
                        print(f"\nUnknown tool: {tool_name} \n")
        if finished or step >= MAX_STEP:
            break

if __name__ == "__main__":
    main()