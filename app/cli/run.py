"""
运行服务命令

启动对话服务器。
"""

import click
from pathlib import Path

from app.shared.config import settings
from app.shared.logger import logger

@click.command("run", help="启动对话服务器")
@click.option("--model","-m",
              type=click.Path(exists=True),  # 类型为路径，且必须存在
              default="models", # 默认值
              help="模型目录或模型文件路径"  #  help 参数用于描述选项的用途
             )

@click.option(
    "--endpoints",
    type=click.Path(exists=True),
    default=None,
    help="API端点配置文件路径"
)
@click.option(
    "--host","-h",
    type=str,
    default="0.0.0.0",
    help="主机地址"
)
@click.option(
    "--port","-p",
    type=int,
    default=settings.defaults.api_port,
    help="服务器监听端口号",
)
@click.option(
    "--cors",
    type=str,
    multiple=True, # 允许多个CORS域名
    default=['*'], # 可以接受所有域名的请求
    help="允许的CORS域名(可多次指定)",
)
# 启用/禁用REST API 调试接口
@click.option(
    "--enable-inspect/--disable-inspect",
    default=True,
    help="启用/禁用REST API 调试接口", 
)
@click.option(
    "--enable-inspect/--disable-inspect",
    default=True,
    help="启用/禁用WebSocket 调试接口", 
)
@click.option(
    "--channel",
    type=click.Choice["rest","socketio","all"],
    help="启用的通道类型", 
    default="all",
)
# 传递上下文对象
@click.pass_context
def run_command(
    ctx:click.Context,
    model:str,
    endpoints:Optional[str] ,
    host:str,
    port:int,
    cors:tuple,
    enable_api:bool,
    enable_inspect:bool,
    channel:str,
) -> None:
    """运行对话服务 启动FastAPI服务器，提供对话API和WebSocket接口"""
    verbose = ctx.obj.get("verbose", False)
    debug = ctx.obj.get("debug", False)

    click.echo("="*80)
    click.echo("启动对话服务")
    click.echo("="*80)

    model_path = Path(model)

    click.echo(f"加载模型: {model_path.absolute()}")
    click.echo(f"加载API端点: {endpoints}")
    click.echo(f"主机地址: {host}")
    click.echo(f"端口号: {port}")
    click.echo(f"调试页面: {'启用' if enable_inspect else '禁用'}")
    click.echo(f"CORS来源:{list(cors)}")
    click.echo()

    try:
        # 导入必要模块
        from app.agent.agent import Agent
        from app.api.server import CustomServiceAgent

        # 加载agent
        click.echo("加载Agent...")

        # 检查是否存在打包的模型或项目目录
        if model_path.is_dir():
            domain_path = model_path / "domain.yml"
            config_path = model_path / "config.yml"
                
            if  domain_path.exists()  and config_path.exists():
                # 从项目目录加载
                agent = Agent.load(str(model_path))
            
            else:
                # 尝试从Models目录加载最新模型
                model_files = list(model_path.glob("*.tar.gz"))
                if model_files:
                    latest_model = max(model_files, key=lambda x: x.stat().st_mtime) # 根据修改时间排序，获取最新模型
                    click.echo(f"加载最新模型: {latest_model.name}")
                    agent = Agent.load(str(latest_model))
                else:
                    click.echo("未找到模型文件，尝试从当前目录加载")
                    agent = Agent.load(".")
            
        else:
            # 模型文件模式
            agent = Agent.load(str(model_path))
        
        click.echo("Agent加载完成")
        
        # 创建服务器
        click.echo("启动服务器...")
        server = CustomServiceAgent(
            agent=agent,
            cors_origins=cors,
            enable_inspect=enable_inspect,
        )
        click.echo()
        click.echo("服务器启动成功,地址: http://{host}:{port}")
        click.echo("使用 --help 查看更多选项")
        click.echo("API 文档: http://{host}:{port}/docs")
        if enable_inspect:
            click.echo("REST API 调试接口: http://{host}:{port}/inspect")
        
        click.echo("按 Ctrl+C 停止服务")
        click.echo("="*80)

        # 启动服务器
        server.run(host=host, port=port)
    
    except KeyboardInterrupt:
        click.echo("\n服务已停止")
    
    except ImportError as e:
        click.echo(f"导入模块失败: {e}")
        if debug:
            raise
        raise SystemExit(1) # 退出程序并返回错误码1
    
    except Exception as e:
        click.echo(f"运行服务失败: {e}")
        if debug:
            raise
        raise SystemExit(1) # 退出程序并返回错误码1

__all__ = ["run_command"]





