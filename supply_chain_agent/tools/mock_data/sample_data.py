"""
Mock data for MCP tools.

This module contains sample data for simulating enterprise APIs.
"""

import datetime

# Order data
ORDER_DATA = {
    "PO-2026-001": {
        "order_id": "PO-2026-001",
        "customer": "ABC科技有限公司",
        "supplier": "XX电子元件有限公司",
        "status": "已发货",
        "amount": 12500.0,
        "currency": "CNY",
        "order_date": "2026-04-15",
        "expected_delivery": "2026-04-25",
        "items": [
            {"sku": "ELEC-001", "description": "电路板", "quantity": 100, "unit_price": 100.0},
            {"sku": "ELEC-002", "description": "电阻器", "quantity": 500, "unit_price": 5.0}
        ],
        "tracking_no": "SF1234567890",
        "warehouse": "上海仓库",
        "priority": "常规"
    },
    "PO-2026-002": {
        "order_id": "PO-2026-002",
        "customer": "DEF制造有限公司",
        "supplier": "YY机械配件厂",
        "status": "生产中",
        "amount": 85000.0,
        "currency": "CNY",
        "order_date": "2026-04-18",
        "expected_delivery": "2026-05-10",
        "items": [
            {"sku": "MECH-001", "description": "传动轴", "quantity": 10, "unit_price": 5000.0},
            {"sku": "MECH-002", "description": "轴承", "quantity": 100, "unit_price": 350.0}
        ],
        "tracking_no": None,
        "warehouse": "广州仓库",
        "priority": "加急"
    },
    "PO-2026-003": {
        "order_id": "PO-2026-003",
        "customer": "GHI贸易公司",
        "supplier": "ZZ包装材料有限公司",
        "status": "待收货",
        "amount": 3200.0,
        "currency": "CNY",
        "order_date": "2026-04-10",
        "expected_delivery": "2026-04-22",
        "items": [
            {"sku": "PACK-001", "description": "纸箱", "quantity": 200, "unit_price": 15.0},
            {"sku": "PACK-002", "description": "气泡膜", "quantity": 50, "unit_price": 4.0}
        ],
        "tracking_no": "YT9876543210",
        "warehouse": "北京仓库",
        "priority": "常规"
    },
    "PO-2026-004": {
        "order_id": "PO-2026-004",
        "customer": "JKL餐饮连锁",
        "supplier": "WW食品原料公司",
        "status": "已取消",
        "amount": 15000.0,
        "currency": "CNY",
        "order_date": "2026-04-05",
        "expected_delivery": "2026-04-20",
        "items": [
            {"sku": "FOOD-001", "description": "冷冻食材", "quantity": 100, "unit_price": 150.0}
        ],
        "tracking_no": None,
        "warehouse": "成都仓库",
        "priority": "常规",
        "cancel_reason": "客户要求"
    }
}

# Logistics data
LOGISTICS_DATA = {
    "SF1234567890": {
        "tracking_no": "SF1234567890",
        "carrier": "顺丰速运",
        "status": "运输中",
        "current_location": "厦门中转场",
        "destination": "上海",
        "sender": "XX电子元件有限公司",
        "receiver": "ABC科技有限公司",
        "weight": 15.5,
        "volume": "0.2m³",
        "events": [
            {
                "timestamp": "2026-04-20 08:30:00",
                "location": "深圳集散中心",
                "description": "快件已揽收",
                "status": "已揽收"
            },
            {
                "timestamp": "2026-04-20 14:15:00",
                "location": "深圳转运中心",
                "description": "快件已发出",
                "status": "运输中"
            },
            {
                "timestamp": "2026-04-21 09:45:00",
                "location": "厦门中转场",
                "description": "快件到达中转场",
                "status": "到达中转场"
            }
        ],
        "eta": "2026-04-23 18:00:00",
        "estimated_days": 1
    },
    "YT9876543210": {
        "tracking_no": "YT9876543210",
        "carrier": "圆通速递",
        "status": "派送中",
        "current_location": "北京市朝阳区",
        "destination": "北京",
        "sender": "ZZ包装材料有限公司",
        "receiver": "GHI贸易公司",
        "weight": 8.2,
        "volume": "0.1m³",
        "events": [
            {
                "timestamp": "2026-04-19 10:20:00",
                "location": "天津分拨中心",
                "description": "快件已揽收",
                "status": "已揽收"
            },
            {
                "timestamp": "2026-04-19 16:45:00",
                "location": "天津转运中心",
                "description": "快件已发出",
                "status": "运输中"
            },
            {
                "timestamp": "2026-04-20 11:30:00",
                "location": "北京分拨中心",
                "description": "快件到达目的地",
                "status": "到达目的地"
            },
            {
                "timestamp": "2026-04-22 08:15:00",
                "location": "北京朝阳区营业部",
                "description": "快件派送中",
                "status": "派送中"
            }
        ],
        "eta": "2026-04-22 17:00:00",
        "estimated_days": 0
    },
    "JD555666777": {
        "tracking_no": "JD555666777",
        "carrier": "京东物流",
        "status": "已签收",
        "current_location": "上海市浦东新区",
        "destination": "上海",
        "sender": "AA电子产品公司",
        "receiver": "BB科技公司",
        "weight": 3.5,
        "volume": "0.05m³",
        "events": [
            {
                "timestamp": "2026-04-18 09:10:00",
                "location": "上海仓库",
                "description": "订单已出库",
                "status": "已出库"
            },
            {
                "timestamp": "2026-04-18 14:30:00",
                "location": "上海浦东分拣中心",
                "description": "包裹分拣完成",
                "status": "分拣完成"
            },
            {
                "timestamp": "2026-04-19 10:45:00",
                "location": "上海浦东新区",
                "description": "快递员开始派送",
                "status": "派送中"
            },
            {
                "timestamp": "2026-04-19 15:20:00",
                "location": "上海市浦东新区",
                "description": "已签收，签收人：前台",
                "status": "已签收"
            }
        ],
        "eta": "已送达",
        "estimated_days": 0
    }
}

# Contract templates
CONTRACT_TEMPLATES = [
    {
        "id": "CT-001",
        "title": "产品质量保证协议",
        "category": "质量协议",
        "content": """产品质量保证协议

甲方：[采购方名称]
乙方：[供应商名称]

鉴于甲方拟向乙方采购产品，为保证产品质量，经双方协商，达成如下协议：

第一条 质量标准
1.1 乙方提供的产品应符合国家标准GB/T 19001-2016《质量管理体系要求》。
1.2 产品应无任何制造缺陷，符合甲方提供的技术规格书要求。

第二条 质保期限
2.1 产品质保期为自验收合格之日起12个月。
2.2 在质保期内，如产品出现质量问题，乙方应在接到通知后24小时内响应。

第三条 违约责任
3.1 如产品不符合质量标准，乙方应承担退货、换货或维修责任。
3.2 因产品质量问题造成甲方损失的，乙方应承担相应的赔偿责任。

第四条 争议解决
4.1 本协议履行过程中发生争议，双方应协商解决。
4.2 协商不成的，可向甲方所在地人民法院提起诉讼。

本协议一式两份，甲乙双方各执一份，自双方签字盖章之日起生效。""",
        "tags": ["质量", "保证", "协议"],
        "version": "2.0",
        "last_updated": "2026-03-15"
    },
    {
        "id": "CT-002",
        "title": "采购合同标准模板",
        "category": "采购合同",
        "content": """采购合同

合同编号：[编号]

甲方（采购方）：[公司名称]
乙方（供应方）：[公司名称]

根据《中华人民共和国民法典》及相关法律法规，甲乙双方本着平等互利的原则，经友好协商，达成如下协议：

第一条 产品规格及数量
1.1 产品名称：[产品名称]
1.2 规格型号：[规格型号]
1.3 数量：[数量]
1.4 单价：[单价]
1.5 总价：[总价]

第二条 交货期限
2.1 交货时间：[具体日期]
2.2 交货地点：[具体地址]
2.3 运输方式：[运输方式]，运输费用由[ ]方承担。

第三条 付款方式
3.1 合同签订后[ ]日内，甲方支付合同总价的[ ]%作为预付款。
3.2 货到验收合格后[ ]日内，甲方支付合同总价的[ ]%。

第四条 验收标准
4.1 验收标准按国家标准或行业标准执行。
4.2 验收期限为货到后[ ]个工作日内。

第五条 其他条款
5.1 未尽事宜，双方协商解决。
5.2 本合同一式两份，甲乙双方各执一份，具有同等法律效力。

甲方（盖章）：            乙方（盖章）：
代表签字：                代表签字：
日期：                    日期：""",
        "tags": ["采购", "合同", "模板"],
        "version": "3.1",
        "last_updated": "2026-02-20"
    },
    {
        "id": "CT-003",
        "title": "保密协议模板",
        "category": "保密协议",
        "content": """保密协议

甲方：[披露方]
乙方：[接收方]

鉴于甲乙双方将在业务合作过程中交换保密信息，为保护双方的合法权益，特签订本保密协议：

第一条 保密信息定义
1.1 保密信息指一方（披露方）向另一方（接收方）披露的、非公开的商业、技术、经营信息。
1.2 包括但不限于：技术资料、客户信息、财务数据、商业计划等。

第二条 保密义务
2.1 接收方应对保密信息予以严格保密，不得向任何第三方披露。
2.2 接收方仅可将保密信息用于本协议约定的合作目的。

第三条 保密期限
3.1 本协议项下的保密义务自本协议生效之日起计算，持续[ ]年。
3.2 保密期限届满后，接收方应继续对核心商业秘密承担保密义务。

第四条 违约责任
4.1 任何一方违反本协议约定，应承担违约责任。
4.2 违约方应赔偿守约方因此遭受的全部损失。

第五条 法律适用
5.1 本协议的订立、效力、解释、履行及争议解决均适用中华人民共和国法律。

本协议一式两份，甲乙双方各执一份，自双方签字盖章之日起生效。""",
        "tags": ["保密", "协议", "模板"],
        "version": "1.5",
        "last_updated": "2026-01-10"
    },
    {
        "id": "CT-004",
        "title": "物流服务合同",
        "category": "物流合同",
        "content": """物流服务合同

委托方（甲方）：[公司名称]
承运方（乙方）：[物流公司名称]

甲乙双方经友好协商，就甲方委托乙方提供物流运输服务事宜达成如下协议：

第一条 服务内容
1.1 乙方为甲方提供货物运输、仓储、配送等服务。
1.2 服务范围：[具体区域]
1.3 运输方式：[公路/铁路/航空/海运]

第二条 服务标准
2.1 运输时效：普通货物[ ]天内送达，加急货物[ ]小时内送达。
2.2 货物安全：乙方应确保货物运输过程中的安全，承担货物毁损、灭失的风险。
2.3 信息反馈：乙方应及时向甲方提供货物跟踪信息。

第三条 费用结算
3.1 运费标准：[具体标准]
3.2 结算周期：每月结算一次，次月[ ]日前结清上月费用。
3.3 支付方式：银行转账。

第四条 保险责任
4.1 乙方应为运输货物购买货物运输保险。
4.2 保险金额不低于货物价值。

第五条 争议解决
5.1 本协议履行过程中发生争议，双方应友好协商解决。
5.2 协商不成的，可向甲方所在地人民法院提起诉讼。

本协议有效期为[ ]年，自[ ]年[ ]月[ ]日至[ ]年[ ]月[ ]日。

甲方（盖章）：            乙方（盖章）：
代表签字：                代表签字：
日期：                    日期：""",
        "tags": ["物流", "运输", "合同"],
        "version": "2.2",
        "last_updated": "2025-12-05"
    }
]

# Work orders
WORK_ORDERS = {
    "WO-2026-001": {
        "work_order_id": "WO-2026-001",
        "order_id": "PO-2026-001",
        "type": "质量检验",
        "status": "待审批",
        "created_by": "质检员-张三",
        "created_date": "2026-04-22",
        "description": "订单PO-2026-001货物到货质量检验申请",
        "priority": "中",
        "estimated_time": "2小时",
        "required_approvals": ["质检主管", "仓库主管"],
        "assigned_to": None,
        "attachments": ["质检报告.pdf", "货物照片.zip"]
    },
    "WO-2026-002": {
        "work_order_id": "WO-2026-002",
        "order_id": "PO-2026-002",
        "type": "生产进度跟踪",
        "status": "处理中",
        "created_by": "生产计划员-李四",
        "created_date": "2026-04-21",
        "description": "跟进订单PO-2026-002的生产进度，确保按时交付",
        "priority": "高",
        "estimated_time": "1天",
        "required_approvals": ["生产经理"],
        "assigned_to": "生产跟踪组",
        "attachments": ["生产计划表.xlsx"]
    },
    "WO-2026-003": {
        "work_order_id": "WO-2026-003",
        "order_id": "PO-2026-003",
        "type": "异常处理",
        "status": "已完成",
        "created_by": "物流专员-王五",
        "created_date": "2026-04-20",
        "description": "处理订单PO-2026-003物流延迟问题",
        "priority": "紧急",
        "estimated_time": "4小时",
        "required_approvals": ["物流经理"],
        "assigned_to": "物流异常处理组",
        "attachments": ["物流异常报告.docx", "沟通记录.pdf"],
        "completion_date": "2026-04-21",
        "completed_by": "物流经理-赵六"
    }
}

# Available work order types
WORK_ORDER_TYPES = [
    {"id": "QT", "name": "质量检验", "description": "产品质量检验与测试"},
    {"id": "PT", "name": "生产跟踪", "description": "生产进度跟踪与协调"},
    {"id": "LE", "name": "物流异常", "description": "物流运输异常处理"},
    {"id": "QD", "name": "质量问题", "description": "产品质量问题处理"},
    {"id": "IN", "name": "入库检验", "description": "货物入库前检验"},
    {"id": "MT", "name": "维护任务", "description": "设备维护与保养"},
    {"id": "UR", "name": "紧急响应", "description": "紧急问题快速响应"}
]

# Issue categories for exception reporting
ISSUE_CATEGORIES = [
    {"id": "LATE", "name": "物流延迟", "description": "货物运输延迟问题"},
    {"id": "DAMAGE", "name": "货物损坏", "description": "货物运输过程中损坏"},
    {"id": "QUALITY", "name": "质量问题", "description": "产品质量不符合标准"},
    {"id": "SUPPLY", "name": "供应短缺", "description": "原材料或零部件短缺"},
    {"id": "PRODUCTION", "name": "生产异常", "description": "生产线异常停运或故障"},
    {"id": "SYSTEM", "name": "系统故障", "description": "ERP/TMS等系统故障"},
    {"id": "OTHER", "name": "其他异常", "description": "其他类型异常问题"}
]

# Priority levels
PRIORITY_LEVELS = [
    {"id": "URGENT", "name": "紧急", "response_time": "1小时内", "color": "red"},
    {"id": "HIGH", "name": "高", "response_time": "4小时内", "color": "orange"},
    {"id": "MEDIUM", "name": "中", "response_time": "8小时内", "color": "yellow"},
    {"id": "LOW", "name": "低", "response_time": "24小时内", "color": "green"}
]

# Sample issues for demonstration
SAMPLE_ISSUES = {
    "ISSUE-2026-001": {
        "issue_id": "ISSUE-2026-001",
        "title": "物流延迟：订单PO-2026-001",
        "category": "物流延迟",
        "priority": "高",
        "description": "订单PO-2026-001预计4月23日送达，目前仍在厦门中转场，预计延迟2天。",
        "affected_order": "PO-2026-001",
        "reported_by": "物流专员-王五",
        "report_date": "2026-04-22",
        "status": "处理中",
        "assigned_to": "物流异常处理组",
        "estimated_resolution": "2026-04-24",
        "attachments": ["物流跟踪截图.png"],
        "updates": [
            {
                "timestamp": "2026-04-22 10:30:00",
                "user": "物流专员-王五",
                "action": "创建问题报告",
                "details": "检测到物流延迟，创建异常报告"
            }
        ]
    },
    "ISSUE-2026-002": {
        "issue_id": "ISSUE-2026-002",
        "title": "产品质量问题：批次A-2026-004",
        "category": "质量问题",
        "priority": "紧急",
        "description": "批次A-2026-004的电路板存在焊接质量问题，不良率约5%。",
        "affected_order": "PO-2026-002",
        "reported_by": "质量检验员-张三",
        "report_date": "2026-04-21",
        "status": "待调查",
        "assigned_to": "质量检验组",
        "estimated_resolution": "2026-04-25",
        "attachments": ["质量检验报告.pdf", "不良品照片.zip"],
        "updates": [
            {
                "timestamp": "2026-04-21 14:15:00",
                "user": "质量检验员-张三",
                "action": "创建问题报告",
                "details": "发现电路板焊接质量问题"
            }
        ]
    }
}