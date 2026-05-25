"""
Flow执行器

负责执行Flow中的步骤。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Text, Any,Optional,TYPE_CHECKING
from app.dialogue_understanding.flow.flow import Flow, FlowsList, FlowStep, StepType
from app.dialogue_understanding.stack.dialogue_stack import FlowStackFrame
if TYPE_CHECKING: # 类型检查时导入 避免循环导入
    from app.core.domain import Domain
    from app.core.tracker import DialogueStateTracker


from app.shared.logger import logger

@dataclass
class ExcutionResult:
    """执行结果"""
    action:Optional[str] = None # 要执行的动作
    slot_to_collect:Optional[str] = None # 要收集的槽位
    events:list[dict[str, Any]] = field(default_factory=list) # 事件列表
    flow_completed:bool = False # Flow是否完成
    next_step_id:Optional[str] = None # 下一个步骤ID
    metadata:dict[str, Any] = field(default_factory=dict) # 元数据

class FlowExecutor:
    """Flow执行器。
    
    负责执行Flow中的步骤，管理Flow的状态转换。
    
    工作流程：
    1. 获取当前Flow和步骤
    2. 根据步骤类型执行相应操作
    3. 确定下一个步骤
    4. 更新状态
    """
    def __init__(self, flows:FlowsList=None, domain:Domain=None) -> None:
        """初始化Flow执行器"""
        self.flows = flows or FlowsList() # 如果没有提供FlowsList，则创建一个空的
        self.domain = domain
    
    def excute_next_step(self, tracker:"DialogueStateTracker") -> ExcutionResult: # 给类型加引号 避免循环导入
        """执行下一个步骤"""
        result = ExcutionResult()
        # 获取当前Flow和步骤
        flow_id = tracker.active_flow
        if not flow_id:
            logger.debug("当前没有活跃的flow，直接返回结果")
            result.flow_completed
            return result
        
        flow = self.flows.get_flow(flow_id)
        if not flow:
            logger.warning("没有找到当前Flow，无法执行下一个步骤")
            result.flow_completed = True
            return result
        
        # 获取当前步骤
        current_step_id = tracker._get_current_step_id(tracker,flow)
        current_step = flow.get_step(current_step_id)

        if not current_step:
            logger.warning("没有找到当前步骤，flow结束...")
            result.flow_completed = True
            return result
        
        # 执行当前步骤
        logger.debug(f"执行当前步骤: {current_step_id} ,当前flow: {flow_id}")

        # 根据步骤类型执行
        if current_step.step_type == StepType.ACTION:
            result = self._execute_action_step(current_step, tracker, flow)
        
        elif current_step.step_type == StepType.COLLECT:
            result = self._execute_collect_step(current_step, tracker, flow)
        
        elif current_step.step_type == StepType.LINK:
            result = self._execute_link_step(current_step, tracker, flow)
        
        elif current_step.step_type == StepType.SET_SLOT:
            result = self._execute_set_slot_step(current_step, tracker, flow)
        
        elif current_step.step_type == StepType.CONDITION:
            result = self._execute_condition_step(current_step, tracker, flow)
               
        elif current_step.step_type == StepType.CALL:
            result = self._execute_call_step(current_step, tracker, flow)
        
        elif current_step.step_type == StepType.END:
            result.flow_completed = True
        
        else:
            logger.warning(f"不支持的步骤类型: {current_step.step_type}")
            result.flow_completed = True
        logger.debug(f"执行当前步骤完成: {current_step_id} ,当前flow: {flow_id}")
        # 返回结果
        return result
        
    
    def _get_current_step_id(self, tracker:"DialogueStateTracker", flow:Flow) -> str:
        """获取当前步骤ID"""
        # 从dialogue_stack中获取当前步骤ID
        flow_frame = tracker.dialogue_stack.find_flow_frame(flow.id)
        if flow_frame:
            step_id = flow_frame.step_id
            # 如果step_id为START，则返回flow的第一个步骤
            if step_id.lower() == "start":
                return flow.get_first_step().id if flow.get_first_step() else step_id
            return step_id
        # 默认返回第一个步骤
        first_step = flow.get_first_step()
        return first_step.id if first_step else "START"

    def _execute_action_step(self, step:FlowStep, tracker:"DialogueStateTracker", flow:Flow) -> ExcutionResult:
        """执行动作步骤"""
        logger.debug(f"开始执行动作步骤: {step.id} ,当前flow: {flow.id} ,动作: {step.action}")
        result = ExcutionResult()
        result.action = step.action
        result.next_step_id = step.next

        # 检查是否结束
        if step.next.lower() == "end" or not step.next:
            logger.debug("动作步骤结束，flow结束...")
            result.flow_completed = True
        logger.debug(f"动作步骤执行完成: {step.id} ,当前flow: {flow.id} ,动作: {step.action}")
        return result
    
    def _execute_collect_step(self, step:FlowStep, tracker:"DialogueStateTracker", flow:Flow) -> ExcutionResult:
        """        
          collect步骤行为：
        - 不指定action：默认先调用 utter_ask_{slot_name}，找不到再调用 action_ask_{slot_name}
        - 显式指定action：直接使用指定的动作（可以是utter_xxx或action_xxx）
        - ask_before_filling: 是否在LLM预填充后仍询问用户确认
          - 语义：第一次进入此步骤时清空槽位并询问，用户填充后继续执行
          - 避免死循环：通过检查 slot_to_collect 判断是否已经询问过"""
        logger.debug(f"开始执行收集步骤: {step.id} ,当前flow: {flow.id} ,槽位: {step.collect}")
        result = ExcutionResult()

        slot_name = step.collect
        if not slot_name:
            logger.warning("collect步骤没有指定槽位，无法执行")
            result.next_step_id = self._resolve_next_step_id(step.next,tracker)
            return result
        
        # 检查槽位是否已经收集过
        current_value = tracker.get_slot(slot_name)

        # 获取 flow_frame， 检查是否正在收集该槽位
        flow_frame = tracker.dialogue_stack.top_flow_frame()
        currently_collecting = flow_frame.slot_to_collect if flow_frame else None

        # 判断是否询问用户
        need_ask = False
        if current_value is None:
            # 槽位为空，需要询问用户
            need_ask = True
        
        elif step.ask_before_filling and currently_collecting != slot_name:
            # ask_before_filling 为 True，且我们还没开始收集这个槽位
            # 说明是第一次进入此步骤，需要清空槽位并询问
            need_ask = True
            # 清空槽位 让用户重新输入
            tracker.set_slot(slot_name, None)
            logger.debug(f"清空槽位 {slot_name} 让用户重新输入")
        
        elif step.ask_before_filling and currently_collecting == slot_name:
            # 已经在收集这个槽位，用户刚刚填充了值
            # 不需要再次询问，应该继续执行
            need_ask = False
            logger.debug(f"已经在收集这个槽位，用户已填充该槽位值，继续执行")
        
        if need_ask:
            # 收集槽位
            result.slot_to_collect = slot_name
            # 确定询问动作
            if step.action:
                # 显式指定action，直接使用
                result.action = step.action
            else:
                # 没有显式指定action，使用默认降级策略
                # 先尝试 utter_ask_{slot_name}，找不到再调用 action_ask_{slot_name}
                result.action = f"utter_ask_{slot_name}"
                result.metadata["fallback_action"] = f"action_ask_{slot_name}"
        else:
            # 槽位已填充且不需要确认，处理条件分支进入下一步
            resloved_next = self._resolve_next_step_id(step.next,tracker)
        
            # 检查是否有嵌套的动作需要执行
            nested_action = result._get_nested_action(step.next,tracker)
            if nested_action:
                # 有嵌套的动作，执行嵌套动作
                result.action = nested_action.get('action')
                result.next_step_id = nested_action.get('next')
                # 嵌套动作有下一步，解析下一步ID
                if result.next_step_id:
                    result.next_step_id = self._resolve_next_step_id(result.next_step_id,tracker)
                logger.debug(f"槽位已填充，执行嵌套动作: {nested_action.get('action')} ,当前flow: {flow.id} ,嵌套动作下一步: {result.next_step_id}")
                
            else:
                # 没有嵌套的动作，直接进入下一步
                result.next_step_id = resloved_next
                logger.debug(f"槽位已填充，直接进入下一步: {result.next_step_id} ,当前flow: {flow.id}")
        
        # 检查是否流程结束
        next_val = self._resolve_next_step_id(step.next,tracker)
        if next_val is None or (isinstance(next_val,str) and next_val.lower() == "end"):
            if not result.action:
                # 没有动作，直接结束流程
                result.flow_completed = True
                logger.debug(f"槽位已填充，没有动作，直接结束流程: {flow.id}")
        logger.debug(f"收集步骤执行完成: {step.id} ,当前flow: {flow.id} ,槽位: {slot_name} ,值: {current_value}")
        return result
    
    def _execute_set_slot_step(self, step:FlowStep, tracker:"DialogueStateTracker", flow:Flow) -> ExcutionResult:
        """设置槽位步骤"""
        logger.debug(f"开始执行设置槽位步骤: {step.id} ,当前flow: {flow.id} ,槽位: {step.set_slot}")
        result = ExcutionResult()

        if step.slot_name and step.slot_value is not None:
            # 设置槽位
            tracker.set_slot(step.slot_name, step.slot_value)
            logger.debug(f"设置槽位: {step.slot_name} ,值: {step.slot_value}")
            result.events.append({
                "event": "slot_set",
                "name": step.slot_name,
                "value": step.slot_value
            })
        result.next_step_id = step.next
        # 检查下一步是否结束
        if result.next_step_id is None or (isinstance(result.next_step_id,str) and result.next_step_id.lower() == "end"):
            result.flow_completed = True
        logger.debug(f"设置槽位步骤执行完成: {step.id} ,当前flow: {flow.id} ,槽位: {step.slot_name} ,值: {step.slot_value}")
        return result
    
    def _execute_condition_step(self, step:FlowStep, tracker:"DialogueStateTracker", flow:Flow) -> ExcutionResult:
        """条件步骤"""
        logger.debug(f"开始执行条件步骤: {step.id} ,当前flow: {flow.id} ,条件: {step.condition}")
        result = ExcutionResult()
        # 评估条件
        condition_met = self._evaluate_condition(step.condition,tracker)
        # 检查条件是否满足 如果满足则进入下一步 否则进入else_next
        if condition_met:

            result.next_step_id = step.next
            logger.debug(f"条件满足，进入下一步: {result.next_step_id} ,当前flow: {flow.id}")
        else:
            result.next_step_id = step.else_
            logger.debug(f"条件不满足，进入else下一步: {result.next_step_id} ,当前flow: {flow.id}")
        logger.debug(f"条件步骤执行完成: {step.id} ,当前flow: {flow.id} ,条件: {step.condition} ,结果: {condition_met}")
        return result
    
    def _execute_link_step(self, step:FlowStep, tracker:"DialogueStateTracker", flow:Flow) -> ExcutionResult:
        """链接步骤 切换到另一个flow"""
        logger.debug(f"开始执行链接步骤: {step.id} ,当前flow: {flow.id} ,链接: {step.link}")
        result = ExcutionResult()

        if step.flow_id:
            # 结束当前flow 
            tracker.end_flow()
            logger.debug(f"结束当前flow: {flow.id}")
            # 开始新的flow
            tracker.start_flow(step.flow_id)
            logger.debug(f"切换到新的flow: {step.flow_id} ,当前flow: {flow.id}")
            result.events.append({
                "event": "flow_switched",
                "from_flow": flow.id,
                "to_flow": step.flow_id
            })
        result.flow_completed = True
        logger.debug(f"链接步骤执行完成: {step.id} ,当前flow: {flow.id} ,链接: {step.link}")
        return result
    
    def _execute_call_step(self, step:FlowStep, tracker:"DialogueStateTracker", flow:Flow) -> ExcutionResult:
        """执行调用步骤（调用子Flow，完成后返回）"""
        logger.debug(f"开始执行调用步骤: {step.id} ,当前flow: {flow.id} ,调用: {step.call}")
        result = ExcutionResult()

        if step.flow_id:
            # 开始新的flow
            tracker.start_flow(step.flow_id)
            logger.debug(f"在call步骤中开始新的flow: {step.flow_id} ,当前flow: {flow.id}")
            result.events.append({
                "event": "sub_flow_called",
                "parent_flow": flow.id,
                "sub_flow": step.flow_id
            })

        logger.debug(f"调用步骤执行完成: {step.id} ,当前flow: {flow.id} ,调用: {step.call}")
        return result

    def _resolve_next_step_id(self, next_value:Any, tracker:"DialogueStateTracker") -> Optional[str]:
        """解析下一步ID 处理next字段可能是str或是list的情况"""
        if next_value is None:
            return None
        
        # 如果是字符串，直接返回
        if isinstance(next_value,str):
            return next_value
        
        # 如果是列表，评价条件找到正确的下一步
        if isinstance(next_value,list):
            for branch in next_value:
                if not isinstance(branch,dict):
                    continue

                # 处理 if -then 分支
                if "if" in branch:
                    condition = branch["if"]
                    if self._evaluate_condition(condition,tracker):
                        then_value = branch["then"]
                        # then 可以是字符串或嵌套的步骤列表
                        if isinstance(then_value,str):
                            return then_value
                        elif isinstance(then_value,list) and then_value:
                            # 返回一个标记，表示需要执行嵌套步骤
                            return f"__nested__{id(then_value)}"
                        return then_value
                # 处理 else 分支
                if "else" in branch:
                    else_value = branch["else"]
                    return else_value if isinstance(else_value,str) else None
        return None

    def _get_nested_action(self, next_value:Any, tracker:"DialogueStateTracker") -> Optional[dict[str,Any]]:
        """获取嵌套动作 当 next 是条件列表且 then 包含嵌套步骤时，返回第一个动作"""
        if not isinstance(next_value,list):
            return None
        
        for branch in next_value:
            if not isinstance(branch,dict):
                continue
            # 处理 if -then 分支
            if "if" in branch:
                condition = branch["if"]
                # 如果条件满足，返回嵌套动作
                if self._evaluate_condition(condition,tracker):

                    then_value = branch.get("then")
                    # then 可以是字符串或嵌套的步骤列表
                    if isinstance(then_value,list) and then_value:
                        first_step = then_value[0]
                        # 如果第一个步骤是字典，且包含action字段，则返回嵌套动作
                        if isinstance(first_step,dict) and "action" in first_step:
                            return {
                                "action": first_step["action"],
                                "next": first_step.get("next")
                            }
                    return None
                # 处理 else 分支
            if "else" in branch:
                return None
        return None
    
    def _evaluate_condition(self, condition:str, tracker:"DialogueStateTracker") -> bool:
        """评估条件 支持简单的槽位检查条件"""
        if not condition:
            return False
        # 简单的槽位检查
        # 格式: slot_name == value 或 slot_name != value 或 slot_name
        # 也支持 slots.slot_name 格式
        condition = condition.strip()

        # 移除 "slots." 前缀（如果有）
        condition = condition.replace("slots.","")
    
        # 检查相等
        if "==" in condition:
            parts = condition.split("==")
            # 如果分割后有2个部分，则检查相等 
            if len(parts) == 2:
                slot_name = parts[0].strip()
                expected_value = parts[1].strip().strip('"\'')
                actual_value = tracker.get_slot(slot_name)
                return str(actual_value) == expected_value
        # 检查不相等
        if "!=" in condition:
            parts = condition.split("!=")
            if len(parts) == 2:
                slot_name = parts[0].strip()
                expected_value = parts[1].strip().strip('"\'')
                actual_value = tracker.get_slot(slot_name)
                return str(actual_value) != expected_value
        # 检查槽位值是否为真（truthy）
        # 当条件只是槽位名时（如 "if: slots.set_receive_info"），检查槽位值是否为真
        slot_value = tracker.get_slot(condition)
        # 处理字符串形式的布尔值
        if isinstance(slot_value,str):
            if slot_value.lower() in ["true","yes","1"]:
                return True
            if slot_value.lower() in ["false","no","0"]:
                return False
        # 返回槽位值的布尔值
        return bool(slot_value)

__all__ = ["FlowExecutor", "ExcutionResult"]       










        





