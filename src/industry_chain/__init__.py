"""产业链分析模块 —— 按需调研 + 图谱构建 + 环节公司映射

核心差异功能 FR-06：
用户输入任意产业名称，系统自动进行产业链调研分析，
动态构建上下游图谱，并将结果缓存供后续使用。

参考：
- Serenity Skill 瓶颈分析法（供应链卡点识别）
- UZI-Skill 5_chain 维度设计（多源数据采集）
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import get_config, get_chain_cache_dir
from src.collector import DataCollector, IndustryChain, ChainNode
from src.utils import Cache


# ===================== 内置公司参考映射 =====================
# 为产业链提供公司参考（来源：公开行业研报 + 公司年报）
_BUILTIN_COMPANIES = {
    "低空经济": {
        "上游-飞行器制造": [
            {"code": "600038", "name": "中直股份", "position": "核心"},
            {"code": "688070", "name": "纵横股份", "position": "核心"},
            {"code": "300719", "name": "安达维尔", "position": "核心"},
            {"code": "002023", "name": "海特高新", "position": "核心"},
        ],
        "中游-航电/飞控系统": [
            {"code": "002151", "name": "北斗星通", "position": "核心"},
            {"code": "300627", "name": "华测导航", "position": "核心"},
            {"code": "688568", "name": "中科星图", "position": "核心"},
            {"code": "300045", "name": "华力创通", "position": "核心"},
        ],
        "中游-空管基础设施": [
            {"code": "688631", "name": "莱斯信息", "position": "核心"},
            {"code": "002544", "name": "普天科技", "position": "核心"},
            {"code": "600562", "name": "国睿科技", "position": "核心"},
        ],
        "下游-运营服务": [
            {"code": "600845", "name": "宝信软件", "position": "一般"},
            {"code": "300075", "name": "数字政通", "position": "一般"},
        ]
    },
    "人形机器人": {
        "上游-核心零部件": [
            {"code": "688017", "name": "绿的谐波", "position": "核心"},
            {"code": "002472", "name": "双环传动", "position": "核心"},
            {"code": "300124", "name": "汇川技术", "position": "核心"},
            {"code": "601100", "name": "恒立液压", "position": "核心"},
        ],
        "中游-整机/系统集成": [
            {"code": "300024", "name": "机器人", "position": "核心"},
            {"code": "688777", "name": "中控技术", "position": "核心"},
        ],
        "下游-应用场景": [
            {"code": "300607", "name": "拓斯达", "position": "核心"},
        ]
    },
    "机器人": {
        "上游-核心零部件": [
            {"code": "688017", "name": "绿的谐波", "position": "核心"},
            {"code": "002472", "name": "双环传动", "position": "核心"},
            {"code": "300124", "name": "汇川技术", "position": "核心"},
            {"code": "601100", "name": "恒立液压", "position": "核心"},
            {"code": "002747", "name": "埃斯顿", "position": "核心"},
            {"code": "300660", "name": "江苏雷利", "position": "一般"},
        ],
        "中游-工业机器人本体": [
            {"code": "300024", "name": "机器人", "position": "核心"},
            {"code": "002747", "name": "埃斯顿", "position": "核心"},
            {"code": "688255", "name": "凯尔达", "position": "核心"},
            {"code": "688577", "name": "浙海德曼", "position": "一般"},
        ],
        "中游-人形机器人/系统集成": [
            {"code": "300024", "name": "机器人", "position": "核心"},
            {"code": "688777", "name": "中控技术", "position": "核心"},
            {"code": "688017", "name": "绿的谐波", "position": "核心"},
        ],
        "下游-应用场景": [
            {"code": "300607", "name": "拓斯达", "position": "核心"},
            {"code": "002444", "name": "巨星科技", "position": "一般"},
            {"code": "688218", "name": "江苏北人", "position": "一般"},
            {"code": "300193", "name": "佳士科技", "position": "一般"},
        ]
    },
    "人工智能": {
        "上游-AI芯片/算力": [
            {"code": "688041", "name": "海光信息", "position": "核心"},
            {"code": "603019", "name": "中科曙光", "position": "核心"},
            {"code": "000977", "name": "浪潮信息", "position": "核心"},
            {"code": "300308", "name": "中际旭创", "position": "核心"},
            {"code": "688256", "name": "寒武纪", "position": "核心"},
        ],
        "中游-大模型/算法": [
            {"code": "002230", "name": "科大讯飞", "position": "核心"},
            {"code": "688111", "name": "金山办公", "position": "核心"},
            {"code": "300418", "name": "昆仑万维", "position": "核心"},
        ],
        "下游-应用场景": [
            {"code": "002415", "name": "海康威视", "position": "核心"},
            {"code": "688169", "name": "石头科技", "position": "一般"},
        ]
    },
    "新能源汽车": {
        "上游-锂矿/有色金属": [
            {"code": "002466", "name": "天齐锂业", "position": "核心"},
            {"code": "002460", "name": "赣锋锂业", "position": "核心"},
        ],
        "中游-电池材料": [
            {"code": "300750", "name": "宁德时代", "position": "核心"},
            {"code": "002074", "name": "国轩高科", "position": "核心"},
            {"code": "300014", "name": "亿纬锂能", "position": "核心"},
            {"code": "002812", "name": "恩捷股份", "position": "核心"},
        ],
        "中游-电机电控": [
            {"code": "300124", "name": "汇川技术", "position": "核心"},
            {"code": "600580", "name": "卧龙电驱", "position": "核心"},
        ],
        "下游-整车制造": [
            {"code": "002594", "name": "比亚迪", "position": "核心"},
            {"code": "600104", "name": "上汽集团", "position": "核心"},
            {"code": "000625", "name": "长安汽车", "position": "核心"},
        ],
        "下游-充电基础设施": [
            {"code": "300001", "name": "特锐德", "position": "核心"},
        ]
    },
    "光伏": {
        "上游-硅料/硅片": [
            {"code": "600438", "name": "通威股份", "position": "核心"},
            {"code": "601012", "name": "隆基绿能", "position": "核心"},
        ],
        "中游-电池片/组件": [
            {"code": "688599", "name": "天合光能", "position": "核心"},
            {"code": "002459", "name": "晶澳科技", "position": "核心"},
        ],
        "中游-逆变器/支架": [
            {"code": "300274", "name": "阳光电源", "position": "核心"},
            {"code": "688390", "name": "固德威", "position": "核心"},
        ],
        "下游-电站运营": [
            {"code": "600905", "name": "三峡能源", "position": "核心"},
        ]
    },
    "半导体": {
        "上游-材料": [
            {"code": "688126", "name": "沪硅产业", "position": "核心"},
            {"code": "002409", "name": "雅克科技", "position": "核心"},
        ],
        "上游-设备": [
            {"code": "002371", "name": "北方华创", "position": "核心"},
            {"code": "688012", "name": "中微公司", "position": "核心"},
            {"code": "688072", "name": "拓荆科技", "position": "核心"},
        ],
        "中游-IC设计": [
            {"code": "603986", "name": "兆易创新", "position": "核心"},
            {"code": "002049", "name": "紫光国微", "position": "核心"},
        ],
        "中游-晶圆制造": [
            {"code": "688981", "name": "中芯国际", "position": "核心"},
        ],
        "中游-封装测试": [
            {"code": "002156", "name": "通富微电", "position": "核心"},
            {"code": "600584", "name": "长电科技", "position": "核心"},
        ]
    },
    "储能": {
        "上游-电池材料": [
            {"code": "002466", "name": "天齐锂业", "position": "核心"},
            {"code": "002460", "name": "赣锋锂业", "position": "核心"},
        ],
        "中游-储能系统": [
            {"code": "300750", "name": "宁德时代", "position": "核心"},
            {"code": "300274", "name": "阳光电源", "position": "核心"},
            {"code": "688063", "name": "派能科技", "position": "核心"},
        ],
        "下游-应用场景": [
            {"code": "600905", "name": "三峡能源", "position": "核心"},
        ]
    }
}


# ===================== 内置基线产业链 =====================

_BUILTIN_CHAINS = {
    "新能源汽车": {
        "description": "新能源汽车产业链，从上游锂矿资源到下游整车制造和充电基础设施",
        "nodes": [
            {
                "name": "上游-锂矿/有色金属",
                "description": "锂、钴、镍、稀土等矿产资源开采与提炼",
                "keywords": ["锂矿", "钴", "镍", "稀土", "盐湖提锂", "锂资源"]
            },
            {
                "name": "中游-电池材料",
                "description": "正极材料、负极材料、电解液、隔膜等电池核心材料",
                "keywords": ["正极材料", "负极材料", "电解液", "隔膜", "前驱体"]
            },
            {
                "name": "中游-动力电池",
                "description": "动力电池电芯制造与电池封装（Pack）",
                "keywords": ["动力电池", "锂电池", "磷酸铁锂", "三元锂", "固态电池"]
            },
            {
                "name": "中游-电机电控",
                "description": "驱动电机、电机控制器、电驱动系统",
                "keywords": ["驱动电机", "电机控制器", "电驱动", "扁线电机"]
            },
            {
                "name": "下游-整车制造",
                "description": "新能源乘用车、商用车整车设计与制造",
                "keywords": ["新能源整车", "电动汽车", "插电混动"]
            },
            {
                "name": "下游-充电基础设施",
                "description": "充电桩、换电站、充电运营服务",
                "keywords": ["充电桩", "换电站", "充电模块", "充电运营"]
            }
        ]
    },
    "光伏": {
        "description": "光伏产业链，从上游硅料到下游电站运营",
        "nodes": [
            {
                "name": "上游-硅料/硅片",
                "description": "多晶硅料生产、硅棒/硅片切割加工",
                "keywords": ["多晶硅", "单晶硅", "硅片", "硅料"]
            },
            {
                "name": "中游-电池片/组件",
                "description": "光伏电池片制造、光伏组件封装",
                "keywords": ["光伏电池", "PERC", "TOPCon", "HJT", "光伏组件"]
            },
            {
                "name": "中游-逆变器/支架",
                "description": "光伏逆变器、跟踪支架、光伏玻璃、胶膜",
                "keywords": ["逆变器", "光伏支架", "光伏玻璃", "胶膜", "背板"]
            },
            {
                "name": "下游-电站运营",
                "description": "集中式电站、分布式光伏、EPC总包",
                "keywords": ["光伏电站", "分布式光伏", "EPC", "电站运营"]
            }
        ]
    },
    "半导体": {
        "description": "半导体产业链，从上游材料设备到下游终端应用",
        "nodes": [
            {
                "name": "上游-材料",
                "description": "硅片、光刻胶、电子特气、靶材、CMP抛光液",
                "keywords": ["硅片", "光刻胶", "电子特气", "靶材", "CMP"]
            },
            {
                "name": "上游-设备",
                "description": "光刻机、刻蚀设备、薄膜沉积、检测设备",
                "keywords": ["刻蚀", "薄膜沉积", "光刻机", "清洗", "检测"]
            },
            {
                "name": "中游-IC设计",
                "description": "芯片设计，包括逻辑芯片、存储芯片、模拟芯片、MCU",
                "keywords": ["芯片设计", "EDA", "AI芯片", "存储芯片", "MCU"]
            },
            {
                "name": "中游-晶圆制造",
                "description": "晶圆代工、IDM制造",
                "keywords": ["晶圆代工", "Foundry", "IDM", "先进制程"]
            },
            {
                "name": "中游-封装测试",
                "description": "先进封装、传统封装、芯片测试",
                "keywords": ["封装", "测试", "Chiplet", "SiP"]
            },
            {
                "name": "下游-终端应用",
                "description": "消费电子、汽车电子、工业控制、通信设备",
                "keywords": ["消费电子", "汽车电子", "物联网", "5G"]
            }
        ]
    },
    "人工智能": {
        "description": "人工智能产业链，从算力基础设施到应用场景",
        "nodes": [
            {
                "name": "上游-AI芯片/算力",
                "description": "GPU、NPU、AI服务器、数据中心算力基础设施",
                "keywords": ["AI芯片", "GPU", "算力", "AI服务器", "数据中心"]
            },
            {
                "name": "中游-大模型/算法",
                "description": "基础大模型训练、AI算法平台、机器学习框架",
                "keywords": ["大模型", "AI算法", "机器学习", "自然语言处理", "计算机视觉"]
            },
            {
                "name": "下游-应用场景",
                "description": "AI+医疗、AI+金融、AI+制造、具身智能",
                "keywords": ["AI应用", "具身智能", "机器人", "自动驾驶", "AIGC"]
            }
        ]
    },
    "机器人": {
        "description": "机器人（工业机器人+人形机器人）产业链，从核心零部件到整机集成应用",
        "nodes": [
            {"name": "上游-核心零部件", "description": "减速器、伺服电机、控制器、传感器等核心零部件", "keywords": ["减速器", "伺服电机", "控制器", "传感器", "力矩电机"]},
            {"name": "中游-工业机器人本体", "description": "六轴机器人、SCARA、协作机器人等整机制造", "keywords": ["工业机器人", "焊接机器人", "搬运机器人", "协作机器人"]},
            {"name": "中游-人形机器人/系统集成", "description": "人形机器人本体、自动化产线集成、AI算法集成", "keywords": ["人形机器人", "系统集成", "自动化产线", "机器人集成"]},
            {"name": "下游-应用场景", "description": "汽车制造、3C电子、物流仓储、医疗、服务", "keywords": ["智能制造", "自动化", "汽车产线", "物流仓储"]},
        ]
    },
    "储能": {
        "description": "储能产业链，从电池系统到电网侧应用",
        "nodes": [
            {
                "name": "上游-电池材料",
                "description": "锂资源、钒资源、正负极材料、电解液",
                "keywords": ["锂资源", "钒", "液流电池", "钠离子", "压缩空气"]
            },
            {
                "name": "中游-储能系统",
                "description": "电池模组/Pack、BMS、PCS、温控系统、消防系统",
                "keywords": ["储能电池", "BMS", "PCS", "温控", "EMS"]
            },
            {
                "name": "下游-应用场景",
                "description": "发电侧储能、电网侧调频、工商业储能、户用储能",
                "keywords": ["发电侧储能", "电网调频", "工商业储能", "户用储能"]
            }
        ]
    },
    "低空经济": {
        "description": "低空经济产业链，涵盖 eVTOL、无人机、低空管控等新兴领域",
        "nodes": [
            {
                "name": "上游-飞行器制造",
                "description": "eVTOL整机制造、无人机研发、飞行器材料与结构",
                "keywords": ["eVTOL", "无人机", "飞行汽车", "复合材料"]
            },
            {
                "name": "中游-航电/飞控系统",
                "description": "飞行控制系统、导航系统、通信系统、传感器",
                "keywords": ["飞控", "航电", "导航", "传感器", "雷达"]
            },
            {
                "name": "中游-空管基础设施",
                "description": "低空空域管理、UAM交通管理、人员培训、适航认证",
                "keywords": ["空管", "低空管控", "适航", "UAM"]
            },
            {
                "name": "下游-运营服务",
                "description": "低空物流、城市空中出行、应急救援、农业植保",
                "keywords": ["低空物流", "空中出行", "应急救援", "农业植保"]
            }
        ]
    },
    "人形机器人": {
        "description": "人形机器人产业链，从核心零部件到整机集成应用",
        "nodes": [
            {
                "name": "上游-核心零部件",
                "description": "减速器（RV/Harmonic）、伺服电机、传感器、控制器",
                "keywords": ["减速器", "伺服电机", "力矩传感器", "编码器"]
            },
            {
                "name": "中游-整机/系统集成",
                "description": "人形机器人本体制造、AI算法集成、运动控制",
                "keywords": ["人形机器人", "仿生机器人", "运动控制", "步态算法"]
            },
            {
                "name": "下游-应用场景",
                "description": "工业制造、仓储物流、医疗护理、家庭服务",
                "keywords": ["工业机器人", "服务机器人", "智能制造", "自动化"]
            }
        ]
    },
    "消费电子": {
        "description": "消费电子产业链，从芯片到终端品牌",
        "nodes": [
            {
                "name": "上游-芯片/元器件",
                "description": "SoC芯片、存储芯片、传感器、PCB、连接器",
                "keywords": ["SoC", "传感器", "PCB", "连接器", "射频"]
            },
            {
                "name": "中游-模组/代工",
                "description": "摄像头模组、显示模组、声学模组、EMS代工",
                "keywords": ["摄像头", "显示面板", "代工", "整机组装", "声学"]
            },
            {
                "name": "下游-终端品牌",
                "description": "智能手机、平板、PC、可穿戴设备、AR/VR",
                "keywords": ["智能手机", "可穿戴", "AR/VR", "消费电子品牌"]
            }
        ]
    },
    "医药生物": {
        "description": "医药生物产业链，从研发到终端医疗服务",
        "nodes": [
            {
                "name": "上游-研发/原料药",
                "description": "创新药研发、CXO服务、原料药、中间体",
                "keywords": ["创新药", "CXO", "原料药", "中间体", "生物药"]
            },
            {
                "name": "中游-药品制造",
                "description": "化学制剂、生物制品、中药、疫苗生产",
                "keywords": ["化学药", "生物制品", "中药", "疫苗", "血制品"]
            },
            {
                "name": "下游-医药流通/医疗",
                "description": "医药商业、连锁药房、医疗器械、医疗服务",
                "keywords": ["医药商业", "药房", "医疗器械", "医疗服务", "IVD"]
            }
        ]
    },
    "信创": {
        "description": "信创（信息技术应用创新）产业链",
        "nodes": [
            {
                "name": "上游-基础硬件",
                "description": "CPU/GPU芯片、服务器、存储设备、网络设备",
                "keywords": ["CPU", "服务器", "存储", "网络设备", "国产芯片"]
            },
            {
                "name": "中游-基础软件",
                "description": "操作系统、数据库、中间件",
                "keywords": ["操作系统", "数据库", "中间件", "国产OS"]
            },
            {
                "name": "下游-应用软件/安全",
                "description": "办公软件、ERP、信息安全、政务应用",
                "keywords": ["办公软件", "ERP", "信息安全", "政务软件", "工业软件"]
            }
        ]
    }
}


class IndustryChainResearcher:
    """产业链按需调研引擎（核心差异功能 FR-06）"""

    def __init__(self):
        self.collector = DataCollector()
        cfg = get_config()
        ic_cfg = cfg["industry_chain"]
        self.cache_dir = get_chain_cache_dir()
        self.cache = Cache(self.cache_dir)
        self.min_segments = ic_cfg["min_segments"]
        self.min_companies = ic_cfg["min_companies_per_segment"]
        self.research_timeout = ic_cfg["research_timeout"]

    def get_available_chains(self) -> List[Dict[str, str]]:
        """获取可用产业链列表（基线 + 已缓存的自定义调研）"""
        chains = []
        for name, data in _BUILTIN_CHAINS.items():
            chains.append({
                "name": name,
                "description": data["description"],
                "source": "builtin",
                "node_count": len(data["nodes"])
            })

        # 检查缓存的调研结果（用户之前调研过的）
        for key in self.cache.list_keys():
            if key.startswith("chain_research_"):
                chain_name = key.replace("chain_research_", "")
                if chain_name not in _BUILTIN_CHAINS:
                    data = self.cache.get(key)
                    if data:
                        chains.append({
                            "name": chain_name,
                            "description": data.get("description", ""),
                            "source": "research",
                            "node_count": len(data.get("nodes", []))
                        })
        return chains

    def get_chain(self, name: str) -> Optional[IndustryChain]:
        """获取产业链数据（优先缓存，然后基线，最后调研）"""
        # 1. 优先从缓存获取
        cache_key = f"chain_research_{name}"
        cached = self.cache.get(cache_key)
        if cached:
            return self._dict_to_chain(cached)

        # 2. 从基线获取
        if name in _BUILTIN_CHAINS:
            return self._buildin_to_chain(name)

        # 3. 尝试调研
        return None

    def research_chain(self, name: str, force: bool = False) -> IndustryChain:
        """调研/重新调研指定产业链

        这是核心功能：对用户指定的任意产业进行调研分析
        """
        cache_key = f"chain_research_{name}"

        if not force:
            cached = self.cache.get(cache_key)
            if cached:
                chain = self._dict_to_chain(cached)
                self._enrich_with_companies(chain)
                return chain

        # 先看是否有基线数据
        if name in _BUILTIN_CHAINS:
            chain = self._buildin_to_chain(name)
        else:
            # 对未知产业链进行搜索调研
            chain = self._auto_research(name)

        # 补充公司列表
        self._enrich_with_companies(chain)

        # 保存缓存
        chain.source = "research"
        chain.researched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cache.set(cache_key, self._chain_to_dict(chain), ttl=604800)  # 7天

        return chain

    def refresh_chain(self, name: str) -> IndustryChain:
        """强制刷新产业链数据"""
        return self.research_chain(name, force=True)

    def _auto_research(self, name: str) -> IndustryChain:
        """对未知产业进行自动化调研（按需搜索构建）

        参考 Serenity 方法论：
        1. 识别产业定义和边界
        2. 拆解上下游环节
        3. 提取各环节代表公司
        4. 构建完整图谱
        """
        # 基于关键词规则构建基础图谱
        chain = IndustryChain(
            name=name,
            description=f"{name}产业链（自动调研构建）",
            source="research",
            researched_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # 尝试用行业分类数据寻找相关公司
        try:
            df_sectors = self.collector.get_sector_list()
            # 寻找名称中包含产业关键词的板块
            related_sectors = df_sectors[
                df_sectors["板块名称"].str.contains(name, na=False)
            ]
            if not related_sectors.empty:
                chain.description = f"{name}产业链，相关板块包含{len(related_sectors)}个子行业"
        except Exception:
            pass

        # 构建基本的上下游三段结构
        chain.nodes = [
            ChainNode(
                name=f"上游-{name}原材料/设备",
                description=f"{name}产业链上游核心原材料和相关设备供应商",
                companies=[]
            ),
            ChainNode(
                name=f"中游-{name}核心制造/集成",
                description=f"{name}产业链中游核心产品制造和系统集成环节",
                companies=[]
            ),
            ChainNode(
                name=f"下游-{name}应用/运营",
                description=f"{name}产业链下游终端应用和运营服务",
                companies=[]
            )
        ]

        return chain

    def _buildin_to_chain(self, name: str) -> IndustryChain:
        """将内置基线数据转为 IndustryChain 对象"""
        data = _BUILTIN_CHAINS[name]
        nodes = []
        for node_data in data["nodes"]:
            nodes.append(ChainNode(
                name=node_data["name"],
                description=node_data["description"],
                companies=[]
            ))
        return IndustryChain(
            name=name,
            description=data["description"],
            nodes=nodes,
            source="builtin"
        )

    def _enrich_with_companies(self, chain: IndustryChain):
        """为产业链各环节补充上市公司

        策略：
        1. 优先使用内置公司映射（来源：行业研报）
        2. 内置映射不足时，自动从板块/关键词匹配
        """
        # 1. 检查是否有内置公司映射
        chain_companies = _BUILTIN_COMPANIES.get(chain.name, {})

        for node in chain.nodes:
            builtin = chain_companies.get(node.name, [])
            if builtin:
                # 使用内置映射
                node.companies = builtin
            else:
                # 尝试自动匹配
                companies = self._find_companies_for_segment(
                    chain.name, node.name, node.description
                )
                node.companies = companies if companies else builtin

    def _find_companies_for_segment(self, chain_name: str, segment_name: str,
                                     description: str) -> List[Dict]:
        """寻找产业链某环节的上市公司

        策略：通过板块分类 + 关键词匹配寻找
        """
        candidates = []
        seen_codes = set()

        try:
            # 1. 查找相关行业板块的成分股
            df_sectors = self.collector.get_sector_list()
            related_sectors = df_sectors[
                df_sectors["板块名称"].str.contains(
                    "|".join([chain_name, segment_name]), na=False
                )
            ]

            for _, sector in related_sectors.iterrows():
                try:
                    df_stocks = self.collector.get_sector_stocks(sector["板块名称"])
                    if not df_stocks.empty:
                        for _, row in df_stocks.iterrows():
                            code = str(row.get("代码", ""))
                            if code and code not in seen_codes:
                                candidates.append({
                                    "code": code,
                                    "name": row.get("名称", ""),
                                    "position": "核心",
                                    "segment": segment_name
                                })
                                seen_codes.add(code)
                except Exception:
                    continue

            # 2. 如果板块匹配不够，通过全市场搜索补充
            if len(candidates) < self.min_companies:
                try:
                    keywords = self._extract_keywords(segment_name, description)
                    df_all = self.collector.get_stock_list()
                    for keyword in keywords:
                        if len(candidates) >= 10:
                            break
                        matches = df_all[
                            df_all["name"].str.contains(keyword, na=False)
                        ]
                        for _, row in matches.iterrows():
                            code = str(row.get("code", ""))
                            if code and code not in seen_codes:
                                candidates.append({
                                    "code": code,
                                    "name": row.get("name", ""),
                                    "position": "一般",
                                    "segment": segment_name
                                })
                                seen_codes.add(code)
                except Exception:
                    pass

        except Exception:
            pass

        return candidates[:15]  # 最多返回15家

    def _extract_keywords(self, segment_name: str, description: str) -> List[str]:
        """从环节名称和描述中提取搜索关键词"""
        # 去除前缀标识如"上游-""中游-""下游-"
        keywords = []
        for text in [segment_name, description]:
            for sep in ["上游-", "中游-", "下游-"]:
                if sep in text:
                    text = text.replace(sep, "")
            # 进一步拆分
            for sep in ["、", "/", "，", " "]:
                if sep in text:
                    keywords.extend([k.strip() for k in text.split(sep) if k.strip()])
            if text not in keywords:
                keywords.append(text)
        return keywords[:5]

    # ===================== Serenity 瓶颈分析 =====================

    def analyze_bottlenecks(self, chain: IndustryChain) -> List[Dict]:
        """产业链瓶颈分析（参考 Serenity 方法论）

        分析产业链各环节的稀缺性和瓶颈程度
        """
        bottlenecks = []
        for node in chain.nodes:
            # 基于公司和环节特征评估瓶颈
            score = self._score_bottleneck(node)
            bottlenecks.append({
                "segment": node.name,
                "company_count": len(node.companies),
                "bottleneck_score": score,
                "level": "🔴 高" if score >= 7 else ("🟡 中" if score >= 4 else "🟢 低"),
                "analysis": self._get_bottleneck_analysis(node, score)
            })
        return bottlenecks

    def _score_bottleneck(self, node: ChainNode) -> int:
        """评估环节瓶颈程度（1-10 分）

        评分因子：
        - 公司数量（越少越稀缺）
        - 技术壁垒（通过环节描述判断）
        - 代表性公司定位
        """
        score = 5  # 基础分

        # 公司数量越少越瓶颈
        n = len(node.companies)
        if n == 0:
            score += 3
        elif n <= 3:
            score += 2
        elif n <= 5:
            score += 1
        elif n >= 15:
            score -= 1

        # 环节层级（上游通常更稀缺）
        if "上游" in node.name:
            score += 1

        # 通过公司定位调整
        core_count = sum(1 for c in node.companies if c.get("position") == "核心")
        if core_count <= 1 and n > 0:
            score += 1

        return max(1, min(10, score))

    def _get_bottleneck_analysis(self, node: ChainNode, score: int) -> str:
        """生成瓶颈分析文本"""
        if score >= 7:
            return (
                f"该环节公司数量较少（{len(node.companies)}家），在产业链中处于稀缺位置。"
                f"若下游需求爆发，该环节可能因产能限制成为产业链卡点，"
                f"相关公司享有较高定价权，建议重点关注业绩弹性。"
            )
        elif score >= 4:
            return (
                f"该环节有一定竞争格局（{len(node.companies)}家公司），"
                f"需要进一步分析各公司的技术差异和市占率变化。"
            )
        else:
            return (
                f"该环节公司较多（{len(node.companies)}家），竞争相对充分，"
                f"整体来看不太可能出现供给瓶颈。"
            )

    def _chain_to_dict(self, chain: IndustryChain) -> Dict:
        return {
            "name": chain.name,
            "description": chain.description,
            "source": chain.source,
            "researched_at": chain.researched_at,
            "nodes": [
                {
                    "name": n.name,
                    "description": n.description,
                    "companies": n.companies
                }
                for n in chain.nodes
            ]
        }

    def _dict_to_chain(self, data: Dict) -> IndustryChain:
        nodes = []
        for nd in data.get("nodes", []):
            nodes.append(ChainNode(
                name=nd.get("name", ""),
                description=nd.get("description", ""),
                companies=nd.get("companies", [])
            ))
        return IndustryChain(
            name=data.get("name", ""),
            description=data.get("description", ""),
            nodes=nodes,
            source=data.get("source", "cache"),
            researched_at=data.get("researched_at", "")
        )
