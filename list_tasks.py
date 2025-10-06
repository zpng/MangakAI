#!/usr/bin/env python3
"""
查询数据库中的所有任务脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db_session
from models.manga_models import MangaTask, MangaPanel, TaskStatus
from sqlalchemy import func
import json
from datetime import datetime

def format_datetime(dt):
    """格式化日期时间"""
    if dt is None:
        return "未设置"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def get_status_display(status):
    """获取状态的中文显示"""
    status_map = {
        TaskStatus.PENDING: "等待处理",
        TaskStatus.PROCESSING: "正在处理", 
        TaskStatus.SCENE_GENERATION: "生成场景描述",
        TaskStatus.IMAGE_GENERATION: "生成图片",
        TaskStatus.PANEL_PROCESSING: "处理面板",
        TaskStatus.UPLOADING: "上传图片",
        TaskStatus.COMPLETED: "已完成",
        TaskStatus.FAILED: "失败",
        TaskStatus.CANCELLED: "已取消"
    }
    return status_map.get(status, status)

def main():
    try:
        with get_db_session() as db:
            # 获取所有任务
            tasks = db.query(MangaTask).order_by(MangaTask.created_at.desc()).all()
            
            print(f'📋 总共找到 {len(tasks)} 个任务')
            print('=' * 100)
            
            if not tasks:
                print("暂无任务记录")
                return
            
            # 按状态分组统计
            status_counts = {}
            for task in tasks:
                status_counts[task.status] = status_counts.get(task.status, 0) + 1
            
            print("📊 任务状态统计:")
            for status, count in status_counts.items():
                print(f"  {get_status_display(status)}: {count} 个")
            print()
            
            # 详细任务列表
            for i, task in enumerate(tasks, 1):
                # 获取面板信息
                panels = db.query(MangaPanel).filter(MangaPanel.task_id == task.id).all()
                completed_panels = len([p for p in panels if p.status == 'COMPLETED'])
                
                print(f"🎯 任务 #{i}")
                print(f"   ID: {task.id}")
                print(f"   用户会话: {task.user_session_id}")
                print(f"   状态: {get_status_display(task.status)} ({task.status})")
                print(f"   进度: {task.progress}%")
                print(f"   面板: {completed_panels}/{task.total_panels} 已完成")
                print(f"   当前面板: {task.current_panel}")
                print(f"   创建时间: {format_datetime(task.created_at)}")
                print(f"   更新时间: {format_datetime(task.updated_at)}")
                
                if task.completed_at:
                    print(f"   完成时间: {format_datetime(task.completed_at)}")
                
                if task.error_message:
                    print(f"   ❌ 错误信息: {task.error_message}")
                
                # 故事预览
                story_preview = task.story_text[:80] + "..." if len(task.story_text) > 80 else task.story_text
                print(f"   📖 故事预览: {story_preview}")
                
                # 面板详情
                if panels:
                    print(f"   📄 面板详情:")
                    for panel in panels:
                        status_icon = "✅" if panel.status == "COMPLETED" else "⏳" if panel.status == "PROCESSING" else "❌" if panel.status == "FAILED" else "⭕"
                        print(f"      {status_icon} 面板 {panel.panel_number}: {panel.status}")
                
                print('-' * 100)
                
    except Exception as e:
        print(f"❌ 查询任务失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()