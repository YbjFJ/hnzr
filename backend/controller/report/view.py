from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import AnalysisReport
from .validate import ReportCreate, ReportUpdate, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])

# 保存报告
@router.post("/", response_model=ReportResponse)
def create_report(report: ReportCreate, db: Session = Depends(get_db)):
    # 将ref_ids列表转换为字符串格式，如 "1,5,12"
    reference_article_ids = ",".join(map(str, report.ref_ids))
    
    # 创建报告
    db_report = AnalysisReport(
        user_id=1,  # 这里应该从认证中获取用户ID，暂时硬编码为1
        title=report.title,
        content=report.content,
        reference_article_ids=reference_article_ids
    )
    
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    
    return db_report

# 获取我的报告列表
@router.get("/", response_model=List[ReportResponse])
def get_reports(db: Session = Depends(get_db)):
    user_id = 1  # 这里应该从认证中获取用户ID，暂时硬编码为1
    reports = db.query(AnalysisReport).filter(
        AnalysisReport.user_id == user_id
    ).order_by(AnalysisReport.created_at.desc()).all()
    
    return reports

# 获取报告详情
@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db)):
    user_id = 1  # 这里应该从认证中获取用户ID，暂时硬编码为1
    report = db.query(AnalysisReport).filter(
        AnalysisReport.id == report_id,
        AnalysisReport.user_id == user_id
    ).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report

# 添加备注
@router.put("/{report_id}", response_model=ReportResponse)
def update_report(report_id: int, report: ReportUpdate, db: Session = Depends(get_db)):
    user_id = 1  # 这里应该从认证中获取用户ID，暂时硬编码为1
    db_report = db.query(AnalysisReport).filter(
        AnalysisReport.id == report_id,
        AnalysisReport.user_id == user_id
    ).first()
    
    if not db_report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # 更新字段
    update_data = report.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_report, field, value)
    
    db.commit()
    db.refresh(db_report)
    
    return db_report
