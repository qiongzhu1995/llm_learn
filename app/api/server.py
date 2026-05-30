"""
FastAPI应用服务器

提供对话系统的Web服务接口，包括：
- REST API端点
- WebSocket实时通信
- 健康检查
- CORS支持
"""

from pydantic import BaseModel
from fastapi import WebSocket,FastAPI,HTTPException,WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional,Any,TYPE_CHECKING
from app.shared.logger import logger
from app.channels.base_channel import UserMessage
if TYPE_CHECKING:
    from app.agent.agent import Agent

# Pydantic模型
class MessageRequest(BaseModel):
    """消息请求模型"""
    sender:str = "user"
    message:str
    metadata:Optional[dict[str,Any]] = None

class MessageResponse(BaseModel):
    """消息响应模型"""
    recipient_id:str 
    text:Optional[str] = None
    buttons:Optional[list[dict[str,Any]]] = None
    image:Optional[str] = None
    custom:Optional[dict[str,Any]] = None

class SessionInfo(BaseModel):
    """会话信息模型"""
    session_id:str
    slots:dict[str,Any]
    latest_message:Optional[dict[str,Any]] = None
    events_count:int

class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status:str 
    version:str
    agent_ready:bool

class CustomServiceAgent():
    """FastAPI应用服务器。
    
    管理Agent实例和Web服务。
    """
    def __init__(self, agent:Optional[Agent] = None,cors_origins:Optional[list[str]] = None,enable_inspect:bool = False):
        self.agent = agent
        self.cors_origins = cors_origins # 跨域请求允许的源列表
        self.enable_inspect = enable_inspect # 是否启用inspect调试

        # websocket 连接管理
        self._ws_connections:dict[str,WebSocket] = {}

        # 创建fastapi应用
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """创建fastapi应用"""
        app = FastAPI(title="Custom Service Agent",
                      version="1.0.0",
                      description="Custom Service Agent API",
                      docs_url="/docs", #
                      redoc_url="/redoc", # redoc文档页面
                      
                      )
        # 添加CORS中间件
        app.add_middleware(
            CORSMiddleware,  # 跨域请求中间件
            allow_origins=self.cors_origins, # 允许的源列表
            allow_credentials=True, # 允许携带凭证
            allow_methods=["*"], # 允许的请求方法
            allow_headers=["*"], # 允许的请求头
        )

        # 注册路由
        self._register_routes(app)

        return app
    
    def _register_routes(self, app:FastAPI) -> None:
        """注册路由"""

        @app.get("/", response_model=HealthResponse)
        async def root():
            """根路径健康检查"""
            from app import __version__ # 当前版本号
            return {
                "status": "ok",
                "version": __version__,
                "agent_ready": self.agent is not None,
            }
        
        @app.get("/health", response_model=HealthResponse)
        async def health_check():
            """健康检查端点"""
            from app import __version__ # 当前版本号
            return {
                "status": "ok",
                "version": __version__,
                "agent_ready": self.agent is not None,
            }
        
        @app.post("/message", response_model=list[MessageResponse])
        async def send_message(request: MessageRequest) -> list[MessageResponse]:
            """发送消息到对话系统"""
            if not self.agent:
                logger.error(" Agent not initialized")
                raise HTTPException(status_code=500, detail="Agent not initialized")

            try:
                # 创建用户消息
                user_message = UserMessage(
                    text=request.message,
                    sender_id=request.sender,
                    input_channel="reset",
                    metadata=request.metadata or {},
                )

                # 处理消息
                response = self.agent.handle_message(
                    message=user_message.text,
                    sender_id=user_message.sender_id,
                    metadata=user_message.metadata,
                )

                # 转换响应格式 
                result = []
                for msg in response.messages:
                    result.append({
                        "recipient_id": request.sender,
                        "text": msg.get("text"),
                        "buttons": msg.get("buttons"),
                        "image": msg.get("image"),
                        "custom": msg.get("custom"),
                    })
                # 广播到所有WebSocket连接
                await self._broadcast_message(
                    sender = result.sender,
                    message={"type": "response", "data": result},
                    )
                logger.info(f"发送消息到{request.sender}: {result}")
                return result
            except Exception as e:
                logger.error(f"处理消息失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get('/api/sessions/{session_id}', response_model=SessionInfo)
        async def get_session_info(session_id:str) -> SessionInfo:
            """获取会话信息"""
            if not self.agent:
                logger.error(" Agent not initialized")
                raise HTTPException(status_code=500, detail="Agent not initialized")
            try:
                tracker = await self.agent.get_tracker(session_id)
                if not tracker:
                    logger.warning(f"tracker会话不存在: {session_id}")
                    raise HTTPException(status_code=404, detail="Tracker not found")
                return SessionInfo(
                    session_id=session_id,
                    slots=tracker.get_all_slots(),
                    latest_message=tracker.latest_message,
                    events_count=len(tracker.dialogue_turns),
                )
            except HTTPException as e:
                logger.error(f"获取会话信息失败: {e}")
                raise e
            except Exception as e:
                logger.error(f"获取会话信息失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
        @app.post("/api/sessions/{session_id}/reset")
        async def reset_session(session_id:str) :
            """重置会话"""
            if not self.agent:
                logger.error(" Agent not initialized")
                raise HTTPException(status_code=500, detail="Agent not initialized")
            try:
                await self.agent.reset_tracker(session_id)
                return {"status": "ok","message": "Session reset successfully"}
            except HTTPException as e:
                logger.error(f"重置会话失败: {e}")
                raise e
        
        @app.get("/api/domain")
        async def get_domain() -> dict[str,Any]:
            """获取domain"""
            if not self.agent:
                logger.error(" Agent not initialized")
                raise HTTPException(status_code=500, detail="Agent not initialized")
            try:
                return self.agent.domain.as_dict()
            except HTTPException as e:
                logger.error(f"获取domain失败: {e}")
                raise e
            except Exception as e:
                logger.error(f"获取domain失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        @app.get("/api/flows")
        async def get_flows() :
            """获取flows"""
            if not self.agent:
                logger.error(" Agent not initialized")
                raise HTTPException(status_code=500, detail="Agent not initialized")
            try:
                flows_data = []
                if self.agent.flows:
                    for flow in self.agent.flows:
                        steps_data = []
                        for step in flow.steps:
                            step_dict = {
                                "id": step.id,
                                "action": step.action,
                                "next_step": step.next,
                                "collect":step.collect,
                                "set_slots":step.set_slots if hasattr(step,"set_slots") else None,
                                "step_type":step.step_type.value if hasattr(step,"step_type") else str(step.step_type),
                            }
                            steps_data.append(step_dict)
                        flows_data.append({
                            "id": flow.id,
                            "description": flow.description,
                            "steps": steps_data,
                        })
                return flows_data
            except HTTPException as e:
                logger.error(f"获取flows失败: {e}")
    
        @app.get("/api/tracker/{session_id}/full")
        async def get_full_tracker(session_id:str) -> dict[str,Any]:
            """获取完整的tracker"""
            if not self.agent:
                logger.error(" Agent not initialized")
                raise HTTPException(status_code=500, detail="Agent not initialized")
            try:
                tracker = await self.agent.get_tracker(session_id)
                if not tracker:
                    logger.warning(f"tracker会话不存在: {session_id}")
                    raise HTTPException(status_code=404, detail="Tracker not found")
                
                # 构建完整的tracker数据
                events = []
                for turn in tracker.dialogue_turns:
                    if turn.user_message:
                        events.append({
                            "event": "user",
                            "text" : turn.user_message.text,
                            "timestamp": turn.timestamp,
                        })
                    for bot_msg in turn.bot_messages:
                        events.append({
                            "event": "bot",
                            "text": bot_msg.text,
                            "timestamp": getattr(bot_msg,"timestamp",None),
                        })

                flow_stack = []
                for frame in turn.bot_messages:
                    from app.dialogue_understanding.stack.stack_frame import FlowStackFrame
                    if isinstance(frame,FlowStackFrame):
                        flow_stack.append({
                            "flow_id": frame.flow_id,
                            "step_id": frame.step_id,
                            "frame_id":frame.frame_id
                        })
                
                # flow 执行历史，包括已完成的
                flow_history = []
                for history in tracker.flow_history:
                    flow_history.append({
                        "flow_id": history.get("flow_name",""),
                        "started_at": history.get("started_at",None),
                        "ended_at": history.get("ended_at",None),
                        "completed": history.get("completed",False),
                    })
                
                return {
                    "session_id": session_id,
                    "slots": tracker.get_all_slots(),
                    "events": events,
                    "flow_stack": flow_stack,
                    "flow_history": flow_history,
                    "active_flow": tracker.active_flow,
                    "latest_message": tracker.latest_action_name,
                    "latest_action": tracker.latest_action_name,
                    "latest_message": {
                        "text": tracker.latest_message.text if tracker.latest_message else None,
                        "timestamp": tracker.latest_message.timestamp if tracker.latest_message else None,
                    } if tracker.latest_message else None

                }
            except HTTPException as e:
                logger.error(f"获取完整的tracker失败: {e}")
                raise e
            except Exception as e:
                logger.error(f"获取完整的tracker失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
        @app.websocket("/api/stream")
        async def websocket_endpoint(websocket:WebSocket):
            """WebSocket实时消息流"""
            await websocket.accept()
            session_id = None

            try:
                while True:
                    # receive_json 等待客户端发送消息
                    data = await websocket.receive_json()  
                    msg_type = data.get("type","message")

                    if msg_type == "connect":
                        session_id = data.get("session_id","default")
                        self._add_ws_connection(session_id,websocket)
                        await websocket.send_json({
                            "type": "connected",
                            "session_id": session_id,
                        })
                    
                    elif msg_type == "message":
                        if not self.agent:
                            logger.error(" Agent not initialized")
                            await websocket.send_json({
                                "type": "error",
                                "message": "Agent not initialized",
                            })
                            continue

                        text = data.get("message",data.get("text",""))
                        sender_id = data.get("sended_id", sender_id or "default")

                        try:
                            response = self.agent.handle_message(
                                message=text,
                                sender_id=sender_id,
                            )
                            
                            await websocket.send_json({
                                "type": "bot_response",
                                "data": response.messages,
                            })
                        except HTTPException as e:
                            logger.error(f"处理实时消息失败: {e}")
                            if session_id:
                                self._remove_ws_connection(session_id,websocket)
                        except Exception as e:
                            logger.error(f"处理实时消息失败: {e}")
                            if session_id:
                                self._remove_ws_connection(session_id,websocket)
                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect as e:
                logger.warning(f"WebSocket连接断开: {e}")
                if session_id:
                    self._remove_ws_connection(session_id,websocket)
            except Exception as e:
                logger.error(f"处理实时消息失败: {e}")
                if session_id:
                    self._remove_ws_connection(session_id,websocket)



    async def _remove_ws_connection(self, session_id:str, websocket:WebSocket) -> None:
        """移除WebSocket连接"""
        logger.info(f"移除WebSocket连接: {session_id}")
        if session_id in self._ws_connections:
            if websocket in self._ws_connections[session_id]:
                self._ws_connections[session_id].remove(websocket)
                logger.info(f"移除WebSocket连接: {session_id}")
            if not self._ws_connections[session_id]:
                del self._ws_connections[session_id]
                logger.info(f"移除WebSocket连接: {session_id}")


    async def _add_ws_connection(self, session_id:str, websocket:WebSocket) -> None:
        """添加WebSocket连接"""
        logger.info(f"添加WebSocket连接: {session_id}")
        if session_id not in self._ws_connections:
            self._ws_connections[session_id] = []
        self._ws_connections[session_id].append(websocket)
            

    async def _broadcast_message(self, sender:str, message:dict[str,Any]) -> None:
        """广播消息到所有WebSocket连接"""
        if sender not in self._ws_connections:
            logger.warning(f"WebSocket连接不存在: {sender}")
            return
        
        disconnected = []
        for ws in self._ws_connections[sender]:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"发送消息到{sender}失败: {e}")
                disconnected.append(ws)
        
        # 清理断开的连接
        for ws in disconnected:
            self._remove_ws_connection(sender,ws)

    
    def _remove_ws_connection(self, sender:str, ws:WebSocket) -> None:
        """移除WebSocket连接"""
        if sender in self._ws_connections :
            if ws in self._ws_connections[sender]:
                self._ws_connections[sender].remove(ws)
                logger.info(f"移除WebSocket连接: {sender}")
            if not self._ws_connections[sender]:
                del self._ws_connections[sender]
                logger.info(f"移除WebSocket连接: {sender}")
    
    






 