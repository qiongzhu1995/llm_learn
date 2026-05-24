# 文件说明：MySQL存储。

from typing import Optional,Iterable,Text
import json
from json import JSONDecodeError

from app.core.stores.tracker_store import TrackerStore
from app.core.domain import Domain
from app.core.tracker import DialogueStateTracker
from app.shared.logger import logger
from app.shared.exceptions import DatabaseConnectionError,DatabaseOperationError,TrackerSerializationError,TrackerStoreException


class MySQLTrackerStore(TrackerStore):
    """MySQL存储Tracker状态"""

    def __init__(self, domain:Optional[Domain] = None,url:Optional[str] = None,**mysql_config:dict) -> None:
        super().__init__(domain)

        self.host = mysql_config.get("host")
        self.port = mysql_config.get("port")
        self.user = mysql_config.get("user")
        self.password = mysql_config.get("password")
        self.db = mysql_config.get("db")
        self.table_name = mysql_config.get("tracker_table_name")
        self.url = url

        self._engine = None
        self._session = None
        self._tracker_table = None
        self._initialized = False

    def _get_connection(self) -> str:
        """
        获取数据库连接URL
        """
        if self.url:
            return self.url
        else:
            return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"
    
    async def _ensure_initialized(self) -> None:
        """
        确保数据库连接已初始化
        """
        if self._initialized:
            return
        
        try:
            from sqlalchemy import create_engine,MetaData,Table,Column,String,Text as SQLText,DateTime,func
            from sqlalchemy.orm import sessionmaker

            # 创建引擎
            conn_url = self._get_connection()
            self._engine = create_engine(
                conn_url,
                pool_pre_ping=True,  # 连接池预ping,避免连接断开
                pool_size=20,  # 连接池大小 
                pool_recycle=3600,  # 连接池回收时间,避免连接长时间占用
                ) # 连接池配置
            # 创建表结构
            metadata = MetaData() # 创建元数据
            self._tracker_table = Table(
                self.table_name, 
                metadata, 
                Column("session_id", String(255), primary_key=True),
                Column("state", SQLText,nullable=False),
                Column("created_at", DateTime,default=func.now()),
                Column("updated_at", DateTime,default=func.now(),onupdate=func.now()), # onupdate:更新时自动更新时间
                )  
            # 创建表
            metadata.create_all(self._engine)

            # 创建会话工厂
            self._session_factory = sessionmaker(bind=self._engine)

            self._initialized = True

            logger.info(f"MySQL连接初始化成功...")
        except Exception as e:
            logger.error(f"MySQL连接初始化失败: {e}")
            raise DatabaseConnectionError(f"MySQL连接初始化失败: {e}")
    
    async def save(self,tracker: DialogueStateTracker) -> None:
        """
        保存对话状态 使用upsert 存在则更新，不存在则插入
        """
        await self._ensure_initialized()
        try:


            # 通用 SQLAlchemy Insert（跨数据库可用），只负责普通 INSERT 语义。
            from sqlalchemy import insert
            # MySQL 方言专用 Insert，支持 on_duplicate_key_update（即 MySQL upsert）。
            from sqlalchemy.dialects.mysql import insert as mysql_insert

            tracker_data = tracker.to_dict()
            state_json = json.dumps(tracker_data,ensure_ascii=False)

            with self._engine.connect() as conn:
                # 创建插入语句
                stmt = mysql_insert(self._tracker_table).values(
                    sender_id=tracker.sender_id,
                    state=state_json,
                )
                # 创建更新语句 使用on_duplicate_key_update 即MySQL upsert
                stmt = stmt.on_duplicate_key_update(
                    state = stmt.inserted.state,
                )
                conn.execute(stmt)
                conn.commit()
                logger.info(f"对话状态保存到MySQL成功...")
        except JSONDecodeError as e:
            logger.error(f"解析Tracker JSON失败: {e}")
            raise TrackerSerializationError(f"解析Tracker JSON失败: {e}")

        except Exception as e:
            logger.error(f"对话状态保存到MySQL失败: {e}")
            raise DatabaseOperationError(f"对话状态保存到MySQL失败: {e}")
    
    async def retrieve(self,sender_id:Text) -> Optional[DialogueStateTracker]:
        """
        从MySQL中检索对话状态
        """
        await self._ensure_initialized()
        try:
            from sqlalchemy import select
            from sqlalchemy.exc import SQLAlchemyError
            from json import JSONDecodeError
            with self._session_factory() as session:
                # c 表示列 
                stmt = select(self._tracker_table.c.state).where(self._tracker_table.c.sender_id == sender_id)
                # fetchone() 返回一个元组，包含单个结果行
                result = session.execute(stmt).fetchone()
                if result is None:
                    logger.warning(f"未找到对话状态: {sender_id}")
                    return None
                state_json = result[0]
                tracker_data = json.loads(state_json)

                domain_slots = self.domain.slots if self.domain else None
                return DialogueStateTracker.from_dict(tracker_data,domain_slots)
        except SQLAlchemyError as e:
            logger.error(f"从MySQL中检索Tracker状态失败: {e}")
            raise DatabaseOperationError(f"从MySQL中检索Tracker状态失败: {e}")
        except JSONDecodeError as e:
            logger.error(f"解析Tracker JSON失败: {e}")
            raise TrackerSerializationError(f"解析Tracker JSON失败: {e}")
        except Exception as e:
            logger.error(f"从MySQL中检索对话状态失败: {e}")
            raise TrackerStoreException(f"从MySQL中检索对话状态失败: {e}")
    
    async def delete(self,sender_id:Text) -> None:
        """
        从MySQL中删除对话状态
        """
        await self._ensure_initialized()
        try:
            from sqlalchemy import delete
            from sqlalchemy.exc import SQLAlchemyError
            with self._session_factory() as session:
                stmt = delete(self._tracker_table).where(self._tracker_table.c.sender_id == sender_id)
                session.execute(stmt)
                session.commit()
                logger.info(f"对话{sender_id}的Tracker状态删除成功...")
        except SQLAlchemyError as e:
            logger.error(f"从MySQL中删除Tracker状态失败: {e}")
            raise DatabaseOperationError(f"从MySQL中删除Tracker状态失败: {e}")
        except Exception as e:
            logger.error(f"从MySQL中删除对话状态失败: {e}")
            raise TrackerStoreException(f"从MySQL中删除对话状态失败: {e}")
    
    async def keys(self) -> Iterable[Text]:
        """
        获取所有会话ID
        """
        await self._ensure_initialized()
        try:
            from sqlalchemy import select
            from sqlalchemy.exc import SQLAlchemyError
            with self._session_factory() as session:
                stmt = select(self._tracker_table.c.sender_id)
                # fetchall() 返回一个列表，包含所有结果行
                result = session.execute(stmt).fetchall()
                return [row[0] for row in result]
        except SQLAlchemyError as e:
            logger.error(f"获取所有session_id列表失败: {e}")
            raise TrackerStoreException(f"获取所有session_id列表失败: {e}")
        except Exception as e:
            logger.error(f"获取所有session_id列表失败: {e}")
            raise TrackerStoreException(f"获取所有session_id列表失败: {e}")
    
    async def close(self) -> None:
        """
        关闭数据库连接
        """
        # SQLAlchemy Engine.dispose() 是同步方法，这里不要使用 await。
        if self._engine is not None:
            self._engine.dispose()
        self._initialized = False
        logger.info(f"MySQL连接关闭成功...")
    
    async def __aenter__(self) -> "MySQLTrackerStore":
        """
        异步上下文管理器 进入上下文时初始化数据库连接
        """
        await self._ensure_initialized()
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """
        异步上下文管理器 退出上下文时关闭数据库连接
        """
        await self.close()
