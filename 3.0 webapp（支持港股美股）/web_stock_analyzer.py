"""
Web版增强股票分析系统 - 支持AI流式输出
基于最新 stock_analyzer.py 修正版本，新增AI流式返回功能
"""

import os
import sys
import logging
import warnings
import pandas as pd
import numpy as np
import json
import math
import copy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
import time
import re
import requests
import xml.etree.ElementTree as ET
import inspect

# 忽略警告
warnings.filterwarnings('ignore')

# 设置日志 - 只输出到命令行
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # 只保留命令行输出
    ]
)

class WebStockAnalyzer:
    """Web版增强股票分析器（基于最新 stock_analyzer.py 修正，支持AI流式输出）"""
    
    def __init__(self, config_file='config.json'):
        """初始化分析器"""
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file
        
        # 加载配置文件
        self.config = self._load_config()
        
        # 缓存配置
        cache_config = self.config.get('cache', {})
        self.cache_duration = timedelta(hours=cache_config.get('price_hours', 1))
        self.fundamental_cache_duration = timedelta(hours=cache_config.get('fundamental_hours', 6))
        self.news_cache_duration = timedelta(hours=cache_config.get('news_hours', 2))
        self.invalid_symbol_cache_duration = timedelta(
            minutes=cache_config.get('invalid_symbol_minutes', 30)
        )
        self.akshare_endpoint_cooldown_duration = timedelta(
            seconds=cache_config.get('akshare_endpoint_cooldown_seconds', 90)
        )
        
        self.price_cache = {}
        self.fundamental_cache = {}
        self.news_cache = {}
        self.invalid_symbol_cache = {}
        self.akshare_endpoint_cooldown = {}
        
        # 分析权重配置
        weights = self.config.get('analysis_weights', {})
        self.analysis_weights = {
            'technical': weights.get('technical', 0.4),
            'fundamental': weights.get('fundamental', 0.4),
            'sentiment': weights.get('sentiment', 0.2)
        }
        
        # 流式推理配置
        streaming = self.config.get('streaming', {})
        self.streaming_config = {
            'enabled': streaming.get('enabled', True),
            'show_thinking': streaming.get('show_thinking', True),
            'delay': streaming.get('delay', 0.1)
        }
        
        # AI配置
        ai_config = self.config.get('ai', {})
        self.ai_config = {
            'max_tokens': ai_config.get('max_tokens', 4000),
            'temperature': ai_config.get('temperature', 0.7),
            'model_preference': ai_config.get('model_preference', 'openai')
        }
        
        # 分析参数配置
        params = self.config.get('analysis_params', {})
        self.analysis_params = {
            'max_news_count': params.get('max_news_count', 100),  # Web版减少新闻数量
            'technical_period_days': params.get('technical_period_days', 180),  # Web版减少分析周期
            'financial_indicators_count': params.get('financial_indicators_count', 25),  # 保持25项指标
            # 主分析模型输入时的新闻压缩配置
            'main_prompt_news_max_items': params.get('main_prompt_news_max_items', 12),
            'main_prompt_news_max_chars': params.get('main_prompt_news_max_chars', 1200)
        }
        
        # API密钥配置
        self.api_keys = self.config.get('api_keys', {})
        
        self.logger.info("Web版股票分析器初始化完成（支持AI流式输出）")
        self._log_config_status()

    def _load_config(self):
        """加载JSON配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                config, updated = self._merge_with_default_config(config)
                if updated:
                    self.logger.info("检测到新增配置项，已自动补全并写回配置文件")
                    self._save_config(config)
                self.logger.info(f"✅ 成功加载配置文件: {self.config_file}")
                return config
            else:
                self.logger.warning(f"⚠️ 配置文件 {self.config_file} 不存在，使用默认配置")
                default_config = self._get_default_config()
                self._save_config(default_config)
                return default_config
                
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ 配置文件格式错误: {e}")
            self.logger.info("使用默认配置并备份错误文件")
            
            if os.path.exists(self.config_file):
                backup_name = f"{self.config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(self.config_file, backup_name)
                self.logger.info(f"错误配置文件已备份为: {backup_name}")
            
            default_config = self._get_default_config()
            self._save_config(default_config)
            return default_config
            
        except Exception as e:
            self.logger.error(f"❌ 加载配置文件失败: {e}")
            return self._get_default_config()

    def _merge_with_default_config(self, current_config):
        """将现有配置与默认配置进行深度合并，补齐新增字段"""
        default_config = self._get_default_config()
        merged_config, updated = self._deep_merge_defaults(current_config, default_config)
        return merged_config, updated

    def _deep_merge_defaults(self, source, defaults):
        """深度合并配置，仅补齐缺失字段，不覆盖用户已配置值"""
        if not isinstance(source, dict):
            return copy.deepcopy(defaults), True

        merged = {}
        updated = False

        for key, default_value in defaults.items():
            if key in source:
                source_value = source[key]
                if isinstance(default_value, dict):
                    merged_value, child_updated = self._deep_merge_defaults(
                        source_value if isinstance(source_value, dict) else {},
                        default_value
                    )
                    merged[key] = merged_value
                    if child_updated or not isinstance(source_value, dict):
                        updated = True
                else:
                    merged[key] = source_value
            else:
                merged[key] = copy.deepcopy(default_value)
                updated = True

        # 保留用户已有的扩展字段
        for key, source_value in source.items():
            if key not in merged:
                merged[key] = source_value

        return merged, updated

    def _get_default_config(self):
        """获取Web版默认配置"""
        return {
            "api_keys": {
                "openai": "",
                "anthropic": "",
                "zhipu": "",
                "siliconflow": "",
                "notes": "请填入您的API密钥"
            },
            "ai": {
                "model_preference": "openai",
                "models": {
                    "openai": "gpt-4o-mini",
                    "anthropic": "claude-3-haiku-20240307",
                    "zhipu": "chatglm_turbo",
                    "siliconflow": "Qwen/Qwen2.5-7B-Instruct"
                },
                "max_tokens": 4000,
                "temperature": 0.7,
                "api_base_urls": {
                    "openai": "https://api.openai.com/v1",
                    "siliconflow": "https://api.siliconflow.cn/v1",
                    "notes": "如使用中转API，修改上述URL"
                },
                "json_mode": {
                    "enabled": False,
                    "provider": "",
                    "model": "",
                    "temperature": 0.2,
                    "max_tokens": 1800,
                    "max_news_items": 30,
                    "notes": "启用后使用JSON模式分析新闻；provider/model留空时默认复用当前结论模型"
                }
            },
            "analysis_weights": {
                "technical": 0.4,
                "fundamental": 0.4,
                "sentiment": 0.2,
                "notes": "权重总和应为1.0"
            },
            "cache": {
                "price_hours": 1,
                "fundamental_hours": 6,
                "news_hours": 2,
                "invalid_symbol_minutes": 30,
                "akshare_endpoint_cooldown_seconds": 90
            },
            "streaming": {
                "enabled": True,
                "show_thinking": False,
                "delay": 0.05
            },
            "analysis_params": {
                "max_news_count": 100,
                "technical_period_days": 180,
                "financial_indicators_count": 25,
                "main_prompt_news_max_items": 12,
                "main_prompt_news_max_chars": 1200
            },
            "web_auth": {
                "enabled": False,
                "password": "",
                "session_timeout": 3600,
                "notes": "Web界面密码鉴权配置"
            },
            "_metadata": {
                "version": "3.2.0-web-streaming-json",
                "created": datetime.now().isoformat(),
                "description": "Web版AI股票分析系统配置文件（支持AI流式输出、港美股、JSON模式新闻分析）"
            }
        }

    def _save_config(self, config):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            self.logger.info(f"✅ 配置文件已保存: {self.config_file}")
        except Exception as e:
            self.logger.error(f"❌ 保存配置文件失败: {e}")

    def _log_config_status(self):
        """记录配置状态"""
        self.logger.info("=== Web版系统配置状态（支持AI流式输出）===")
        
        # 检查API密钥状态
        available_apis = []
        for api_name, api_key in self.api_keys.items():
            if api_name != 'notes' and api_key and api_key.strip():
                available_apis.append(api_name)
        
        if available_apis:
            self.logger.info(f"🤖 可用AI API: {', '.join(available_apis)}")
            primary = self.config.get('ai', {}).get('model_preference', 'openai')
            self.logger.info(f"🎯 主要API: {primary}")
            self.logger.info(f"🌊 AI流式输出: 支持")
            
            # 显示自定义配置
            api_base = self.config.get('ai', {}).get('api_base_urls', {}).get(primary)
            default_api_base = {
                'openai': 'https://api.openai.com/v1',
                'siliconflow': 'https://api.siliconflow.cn/v1'
            }.get(primary)
            if api_base and api_base != default_api_base:
                self.logger.info(f"🔗 自定义API地址({primary}): {api_base}")
        else:
            self.logger.warning("⚠️ 未配置任何AI API密钥")

        json_mode_cfg = self.config.get('ai', {}).get('json_mode', {})
        if json_mode_cfg.get('enabled', False):
            provider, model = self._resolve_json_mode_target()
            self.logger.info(f"🧩 JSON新闻分析: 已启用 ({provider} / {model})")
        else:
            self.logger.info("🧩 JSON新闻分析: 未启用")

        self.logger.info(f"📊 财务指标数量: {self.analysis_params['financial_indicators_count']}")
        self.logger.info(f"📰 最大新闻数量: {self.analysis_params['max_news_count']}")
        self.logger.info(f"📈 技术分析周期: {self.analysis_params['technical_period_days']} 天")
        self.logger.info("🌍 支持市场: A股 / 港股 / 美股")
        
        # 检查Web鉴权配置
        web_auth = self.config.get('web_auth', {})
        if web_auth.get('enabled', False):
            self.logger.info(f"🔐 Web鉴权: 已启用")
        else:
            self.logger.info(f"🔓 Web鉴权: 未启用")
        
        self.logger.info("=" * 40)

    def _market_label(self, market):
        """将市场代码转换为可读名称"""
        mapping = {
            'cn_a': 'A股',
            'hk': '港股',
            'us': '美股'
        }
        return mapping.get(market, '未知市场')

    def _normalize_stock_code(self, stock_code):
        """规范化股票代码并识别市场"""
        raw = str(stock_code or '').strip()
        cleaned = raw.upper().replace(' ', '')

        if not cleaned:
            return {
                'input': raw,
                'market': 'cn_a',
                'market_label': self._market_label('cn_a'),
                'ak_symbol': '',
                'display_code': ''
            }

        # 美股特殊格式: 105.MSFT / 106.TSLA
        # 注意先排除港股 .HK，避免误判
        if re.match(r'^\d+\.[A-Z][A-Z0-9\.\-]{0,15}$', cleaned) and not cleaned.endswith('.HK'):
            ticker = cleaned.split('.', 1)[1]
            return {
                'input': raw,
                'market': 'us',
                'market_label': self._market_label('us'),
                'ak_symbol': cleaned,
                'display_code': ticker
            }

        # 港股常见格式: 00700 / 700 / 00700.HK / HK00700
        if cleaned.endswith('.HK'):
            hk_symbol = re.sub(r'\D', '', cleaned.split('.', 1)[0]).zfill(5)[-5:]
            return {
                'input': raw,
                'market': 'hk',
                'market_label': self._market_label('hk'),
                'ak_symbol': hk_symbol,
                'display_code': f"{hk_symbol}.HK"
            }
        if cleaned.startswith('HK') and cleaned[2:].isdigit():
            hk_symbol = cleaned[2:].zfill(5)[-5:]
            return {
                'input': raw,
                'market': 'hk',
                'market_label': self._market_label('hk'),
                'ak_symbol': hk_symbol,
                'display_code': f"{hk_symbol}.HK"
            }
        if cleaned.isdigit() and 1 <= len(cleaned) <= 5:
            hk_symbol = cleaned.zfill(5)
            return {
                'input': raw,
                'market': 'hk',
                'market_label': self._market_label('hk'),
                'ak_symbol': hk_symbol,
                'display_code': f"{hk_symbol}.HK"
            }

        # A股常见格式: 600519 / sh600519 / 600519.SH
        if cleaned.endswith(('.SH', '.SZ', '.BJ')):
            cn_symbol = re.sub(r'\D', '', cleaned.split('.', 1)[0]).zfill(6)[-6:]
            return {
                'input': raw,
                'market': 'cn_a',
                'market_label': self._market_label('cn_a'),
                'ak_symbol': cn_symbol,
                'display_code': cn_symbol
            }
        if cleaned.startswith(('SH', 'SZ', 'BJ')) and cleaned[2:].isdigit():
            cn_symbol = cleaned[2:].zfill(6)[-6:]
            return {
                'input': raw,
                'market': 'cn_a',
                'market_label': self._market_label('cn_a'),
                'ak_symbol': cn_symbol,
                'display_code': cn_symbol
            }
        if cleaned.isdigit() and len(cleaned) == 6:
            return {
                'input': raw,
                'market': 'cn_a',
                'market_label': self._market_label('cn_a'),
                'ak_symbol': cleaned,
                'display_code': cleaned
            }

        # 默认按美股ticker处理
        us_symbol = cleaned.replace('.US', '')
        return {
            'input': raw,
            'market': 'us',
            'market_label': self._market_label('us'),
            'ak_symbol': us_symbol,
            'display_code': us_symbol
        }

    def _get_us_symbol_candidates(self, ak_symbol):
        """构造美股代码候选列表，兼容akshare不同格式并尽量避免误映射"""
        normalized = str(ak_symbol or '').upper().strip()
        if not normalized:
            return []

        if re.match(r'^\d+\.[A-Z][A-Z0-9\.\-]{0,15}$', normalized):
            return [normalized]

        ticker = normalized.replace('.US', '')
        # 仅构造轻量候选，不再拉取全市场symbol列表，避免慢查询
        candidates = [
            f"105.{ticker}",
            f"106.{ticker}",
            f"107.{ticker}"
        ]

        dedup = []
        for item in candidates:
            if item and item not in dedup:
                dedup.append(item)
        return dedup

    def _standardize_price_columns(self, stock_data):
        """标准化价格数据列，兼容akshare列名和顺序变化"""
        if stock_data is None or stock_data.empty:
            return stock_data

        rename_map = {}
        known_name_map = {
            '日期': 'date',
            '时间': 'date',
            'date': 'date',
            'datetime': 'date',
            '代码': 'code',
            '股票代码': 'code',
            'symbol': 'code',
            '开盘': 'open',
            'open': 'open',
            '收盘': 'close',
            'close': 'close',
            '最高': 'high',
            'high': 'high',
            '最低': 'low',
            'low': 'low',
            '成交量': 'volume',
            'volume': 'volume',
            '成交额': 'turnover',
            'turnover': 'turnover',
            '振幅': 'amplitude',
            'amplitude': 'amplitude',
            '涨跌幅': 'change_pct',
            'change_percent': 'change_pct',
            'change_pct': 'change_pct',
            '涨跌额': 'change_amount',
            'change_amount': 'change_amount',
            '换手率': 'turnover_rate',
            'turnover_rate': 'turnover_rate'
        }

        for col in stock_data.columns:
            col_str = str(col)
            key = col_str.strip().lower()
            mapped = known_name_map.get(col_str) or known_name_map.get(key)
            if not mapped:
                # 兼容部分英文字段（大小写和特殊字符）
                normalized_key = re.sub(r'[^a-z_]', '', key)
                mapped = known_name_map.get(normalized_key)
            if mapped:
                rename_map[col] = mapped

        normalized = stock_data.rename(columns=rename_map)

        # 列名识别不到时退回位置映射
        required_columns = ['open', 'close', 'high', 'low', 'volume']
        missing_columns = [c for c in required_columns if c not in normalized.columns]
        if missing_columns and len(normalized.columns) >= 6:
            cols = list(normalized.columns)
            position_map = {}
            if 'code' in [str(c).lower() for c in cols[:2]]:
                position_map = {
                    cols[0]: 'date',
                    cols[1]: 'code',
                    cols[2]: 'open',
                    cols[3]: 'close',
                    cols[4]: 'high',
                    cols[5]: 'low'
                }
                if len(cols) > 6:
                    position_map[cols[6]] = 'volume'
            else:
                position_map = {
                    cols[0]: 'date',
                    cols[1]: 'open',
                    cols[2]: 'close',
                    cols[3]: 'high',
                    cols[4]: 'low'
                }
                if len(cols) > 5:
                    position_map[cols[5]] = 'volume'

            normalized = normalized.rename(columns=position_map)
            self.logger.info(f"✓ 应用位置列映射: {position_map}")

        return normalized

    def _get_us_data_from_yahoo_chart(self, ticker, start_date, end_date):
        """使用Yahoo Chart接口获取美股历史行情，避免代码歧义映射"""
        meta = {
            'invalid_symbol': False,
            'error_type': '',
            'error_message': ''
        }

        try:
            ticker = str(ticker or '').upper().strip()
            if not ticker:
                meta['invalid_symbol'] = True
                meta['error_type'] = 'empty_symbol'
                meta['error_message'] = '美股代码为空'
                return pd.DataFrame(), meta

            if re.match(r'^\d+\.[A-Z0-9\.\-]+$', ticker):
                ticker = ticker.split('.', 1)[1]

            start_dt = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d') + timedelta(days=1)
            period1 = int(start_dt.timestamp())
            period2 = int(end_dt.timestamp())

            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {
                'period1': period1,
                'period2': period2,
                'interval': '1d',
                'events': 'history',
                'includeAdjustedClose': 'true'
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }

            # 使用连接/读取分离超时，避免单次调用长时间阻塞
            response = requests.get(url, params=params, headers=headers, timeout=(3, 8))
            response.raise_for_status()

            payload = response.json()
            chart = payload.get('chart', {})
            error_obj = chart.get('error')
            if error_obj:
                error_code = str(error_obj.get('code', '')).strip()
                error_desc = str(error_obj.get('description', '')).strip()
                meta['error_type'] = 'symbol_error'
                meta['error_message'] = f"{error_code}: {error_desc}".strip(': ')
                # Yahoo明确返回symbol级错误时，直接判定为无效代码，避免继续慢回退
                lowered_desc = error_desc.lower()
                if error_code in {'Not Found', 'Bad Request'} or 'delisted' in lowered_desc or 'no data found' in lowered_desc:
                    meta['invalid_symbol'] = True
                return pd.DataFrame(), meta

            results = chart.get('result', [])
            if not results:
                meta['error_type'] = 'empty_result'
                meta['error_message'] = 'Yahoo Chart返回为空'
                return pd.DataFrame(), meta

            result = results[0]
            timestamps = result.get('timestamp', [])
            quote = (result.get('indicators', {}) or {}).get('quote', [])
            if not timestamps or not quote:
                meta['error_type'] = 'empty_quote'
                meta['error_message'] = 'Yahoo Chart缺少行情字段'
                return pd.DataFrame(), meta

            quote_data = quote[0]
            df = pd.DataFrame({
                'date': pd.to_datetime(timestamps, unit='s', errors='coerce'),
                'open': quote_data.get('open', []),
                'high': quote_data.get('high', []),
                'low': quote_data.get('low', []),
                'close': quote_data.get('close', []),
                'volume': quote_data.get('volume', [])
            })
            df = df.dropna(subset=['date', 'close'])
            if df.empty:
                meta['error_type'] = 'empty_dataframe'
                meta['error_message'] = 'Yahoo Chart返回数据为空'
                return pd.DataFrame(), meta

            df['turnover'] = None
            df['amplitude'] = (df['high'] - df['low']) / df['close'].replace(0, np.nan) * 100
            df['change_amount'] = df['close'].diff()
            df['change_pct'] = df['close'].pct_change() * 100
            df['turnover_rate'] = None

            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amplitude', 'change_amount', 'change_pct']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.set_index('date').sort_index()
            return df, meta
        except requests.Timeout as timeout_error:
            meta['error_type'] = 'timeout'
            meta['error_message'] = str(timeout_error)
            self.logger.info(f"Yahoo Chart美股行情获取超时: {timeout_error}")
            return pd.DataFrame(), meta
        except Exception as e:
            meta['error_type'] = 'request_error'
            meta['error_message'] = str(e)
            self.logger.info(f"Yahoo Chart美股行情获取失败: {e}")
            return pd.DataFrame(), meta

    def get_stock_data(self, stock_code, period='1y', _retry=0):
        """获取股票价格数据（修正版本）"""
        stock_meta = self._normalize_stock_code(stock_code)
        cache_key = f"{stock_meta['market']}:{stock_meta['ak_symbol']}"

        if cache_key in self.price_cache:
            cache_time, data = self.price_cache[cache_key]
            if datetime.now() - cache_time < self.cache_duration:
                self.logger.info(f"使用缓存的价格数据: {stock_meta['display_code']}")
                return data

        try:
            import akshare as ak

            end_date = datetime.now().strftime('%Y%m%d')
            days = self.analysis_params.get('technical_period_days', 180)
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

            market = stock_meta['market']
            ak_symbol = stock_meta['ak_symbol']
            display_code = stock_meta['display_code']
            self.logger.info(
                f"正在获取 {display_code} ({stock_meta['market_label']}) 历史数据 (过去{days}天)..."
            )

            stock_data = pd.DataFrame()

            if market == 'cn_a':
                stock_data = self._call_akshare_api(
                    'stock_zh_a_hist',
                    retries=3,
                    symbol=ak_symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
            elif market == 'hk':
                stock_data = self._call_akshare_api(
                    'stock_hk_hist',
                    retries=3,
                    symbol=ak_symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
            else:
                last_error = None
                invalid_cache_key = f"us_invalid:{ak_symbol}"
                invalid_cache_time = self.invalid_symbol_cache.get(invalid_cache_key)
                if (
                    invalid_cache_time
                    and datetime.now() - invalid_cache_time < self.invalid_symbol_cache_duration
                ):
                    raise ValueError(f"无效美股代码（缓存）: {display_code}")

                # 美股优先走Yahoo单票接口，确保不会触发全市场同步逻辑
                self.logger.info(f"美股采用单票行情接口，不进行全市场同步: {display_code}")
                yahoo_data, yahoo_meta = self._get_us_data_from_yahoo_chart(
                    ticker=ak_symbol,
                    start_date=start_date,
                    end_date=end_date
                )
                if yahoo_data is not None and not yahoo_data.empty:
                    stock_data = yahoo_data
                    self.invalid_symbol_cache.pop(invalid_cache_key, None)
                    self.logger.info(f"✓ 美股行情使用Yahoo Chart: {display_code}")
                else:
                    if yahoo_meta.get('invalid_symbol'):
                        self.invalid_symbol_cache[invalid_cache_key] = datetime.now()
                        raise ValueError(f"无效美股代码: {display_code}")

                    # 仅在Yahoo网络级失败时回退akshare，且限制耗时
                    last_error = yahoo_meta.get('error_message') or None
                    us_fallback_deadline = time.time() + 6
                    for us_symbol in self._get_us_symbol_candidates(ak_symbol):
                        if time.time() > us_fallback_deadline:
                            self.logger.info("美股akshare回退超过6秒，终止后续候选尝试")
                            break
                        try:
                            stock_data = self._call_akshare_api(
                                'stock_us_hist',
                                retries=1,
                                symbol=us_symbol,
                                period="daily",
                                start_date=start_date,
                                end_date=end_date,
                                adjust=""
                            )
                            if stock_data is not None and not stock_data.empty:
                                self.logger.info(f"✓ 美股代码映射成功: {display_code} -> {us_symbol}")
                                break
                        except Exception as us_error:
                            last_error = us_error
                            stock_data = pd.DataFrame()

                    if (stock_data is None or stock_data.empty) and last_error:
                        raise ValueError(f"美股数据获取失败: {last_error}")

            if stock_data is None or stock_data.empty:
                raise ValueError(f"无法获取股票 {display_code} 的数据")

            self.logger.info(f"获取到 {len(stock_data.columns)} 列数据，原始列名: {list(stock_data.columns)}")
            stock_data = self._standardize_price_columns(stock_data)
            self.logger.info(f"标准化后列名: {list(stock_data.columns)}")

            required_columns = ['close', 'open', 'high', 'low', 'volume']
            missing_columns = []
            for col in required_columns:
                if col not in stock_data.columns:
                    similar_cols = [c for c in stock_data.columns if col in str(c).lower()]
                    if similar_cols:
                        stock_data[col] = stock_data[similar_cols[0]]
                        self.logger.info(f"✓ 自动映射列 {similar_cols[0]} -> {col}")
                    else:
                        missing_columns.append(col)

            if missing_columns:
                self.logger.warning(f"价格数据缺少必要列: {missing_columns}")

            # 处理日期列
            try:
                if 'date' in stock_data.columns:
                    stock_data['date'] = pd.to_datetime(stock_data['date'], errors='coerce')
                    stock_data = stock_data.dropna(subset=['date']).set_index('date')
                else:
                    stock_data.index = pd.to_datetime(stock_data.index, errors='coerce')
                    stock_data = stock_data[~stock_data.index.isna()]
            except Exception as date_error:
                self.logger.warning(f"日期处理失败: {date_error}")

            # 数值列转换
            for col in required_columns + ['change_pct', 'change_amount', 'turnover_rate', 'turnover', 'amplitude']:
                if col in stock_data.columns:
                    stock_data[col] = pd.to_numeric(stock_data[col], errors='coerce')

            if 'close' not in stock_data.columns or stock_data['close'].dropna().empty:
                raise ValueError(f"股票 {display_code} 缺少可用收盘价数据")

            latest_close = stock_data['close'].dropna().iloc[-1]
            latest_open = (
                stock_data['open'].dropna().iloc[-1]
                if 'open' in stock_data.columns and not stock_data['open'].dropna().empty
                else 0
            )
            self.logger.info(f"✓ 数据验证 - 最新收盘价: {latest_close}, 最新开盘价: {latest_open}")

            if pd.isna(latest_close) or float(latest_close) <= 0:
                raise ValueError(f"股票 {display_code} 的收盘价数据异常: {latest_close}")

            self.price_cache[cache_key] = (datetime.now(), stock_data)
            self.logger.info(f"✓ 成功获取 {display_code} 价格数据，共 {len(stock_data)} 条记录")
            return stock_data

        except Exception as e:
            self.logger.error(f"获取股票数据失败({stock_meta['display_code']}): {str(e)}")
            should_retry = _retry < 1 and "无效美股代码" not in str(e)
            # 美股路径已经包含Yahoo+akshare回退，不再做外层重试，避免长尾耗时翻倍
            if stock_meta.get('market') == 'us':
                should_retry = False
            if should_retry:
                self.logger.info(f"价格数据获取重试: {stock_meta['display_code']} (第{_retry + 1}次)")
                time.sleep(0.6)
                return self.get_stock_data(stock_code, period=period, _retry=_retry + 1)
            return pd.DataFrame()

    def _get_empty_fundamental_data(self):
        """获取空的基本面数据结构"""
        return {
            'basic_info': {},
            'financial_indicators': {},
            'valuation': {},
            'performance_forecast': [],
            'dividend_info': [],
            'industry_analysis': {}
        }

    def _is_transient_network_error(self, error):
        """判断是否为可暂时冷却的网络波动错误"""
        text = str(error or '').lower()
        markers = (
            'connection aborted',
            'remotedisconnected',
            'read timed out',
            'connect timeout',
            'connection reset',
            'temporarily unavailable',
            'max retries exceeded'
        )
        return any(marker in text for marker in markers)

    def _call_akshare_api(self, func_names, retries=2, retry_delay=0.5, log_failure=True, **kwargs):
        """兼容调用akshare接口：自动过滤不支持参数并重试"""
        try:
            import akshare as ak
        except Exception as import_error:
            if log_failure:
                self.logger.warning(f"导入akshare失败: {import_error}")
            return None

        names = func_names if isinstance(func_names, (list, tuple)) else [func_names]
        last_error = None
        attempted = False

        for func_name in names:
            if not hasattr(ak, func_name):
                continue

            cooldown_until = self.akshare_endpoint_cooldown.get(func_name)
            if cooldown_until and datetime.now() < cooldown_until:
                continue

            func = getattr(ak, func_name)
            call_kwargs = dict(kwargs)

            try:
                sig = inspect.signature(func)
                params = sig.parameters
                accept_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
                if not accept_var_kw:
                    call_kwargs = {k: v for k, v in call_kwargs.items() if k in params}
            except Exception:
                pass

            for attempt in range(retries):
                attempted = True
                try:
                    if call_kwargs:
                        result = func(**call_kwargs)
                    else:
                        result = func()

                    if result is None and attempt < retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    return result
                except TypeError:
                    # 参数不匹配时尝试无参调用一次
                    try:
                        result = func()
                        if result is None and attempt < retries - 1:
                            time.sleep(retry_delay * (attempt + 1))
                            continue
                        return result
                    except Exception as type_error:
                        last_error = type_error
                        if self._is_transient_network_error(type_error):
                            self.akshare_endpoint_cooldown[func_name] = (
                                datetime.now() + self.akshare_endpoint_cooldown_duration
                            )
                except Exception as call_error:
                    last_error = call_error
                    if self._is_transient_network_error(call_error):
                        self.akshare_endpoint_cooldown[func_name] = (
                            datetime.now() + self.akshare_endpoint_cooldown_duration
                        )

                if attempt < retries - 1:
                    time.sleep(retry_delay * (attempt + 1))

        if last_error and log_failure:
            self.logger.info(f"akshare接口调用失败({names}): {last_error}")
        elif not attempted and log_failure:
            self.logger.info(f"akshare接口冷却中，跳过调用({names})")
        return None

    def _filter_dataframe_by_symbol(self, df, symbol):
        """从DataFrame中过滤指定股票代码的记录"""
        try:
            if df is None or getattr(df, 'empty', True):
                return df

            symbol_text = str(symbol or '').strip().upper()
            if not symbol_text:
                return df

            candidates = [
                symbol_text,
                symbol_text.zfill(6),
                symbol_text[-6:],
                symbol_text[-5:],
                symbol_text[-4:]
            ]
            candidates = [c for c in candidates if c]

            for col in df.columns:
                col_name = str(col).lower()
                if any(k in col_name for k in ['代码', '股票', 'symbol', 'code', '证券']):
                    col_values = df[col].astype(str).str.upper()
                    mask = False
                    for item in candidates:
                        mask = mask | col_values.str.contains(re.escape(item), na=False)
                    filtered = df[mask]
                    if not filtered.empty:
                        return filtered

            return df
        except Exception:
            return df

    def _convert_to_hot_rank_symbol(self, symbol):
        """将A股代码转为热榜接口常见格式，例如 SZ000001/SH600000"""
        code = str(symbol or '').strip()
        if not code.isdigit() or len(code) != 6:
            return code
        if code.startswith('6'):
            return f"SH{code}"
        if code.startswith(('4', '8')):
            return f"BJ{code}"
        return f"SZ{code}"

    def get_comprehensive_fundamental_data(self, stock_code):
        """获取25项综合财务指标数据（修正版本）"""
        stock_meta = self._normalize_stock_code(stock_code)
        cache_key = f"{stock_meta['market']}:{stock_meta['ak_symbol']}"
        if cache_key in self.fundamental_cache:
            cache_time, data = self.fundamental_cache[cache_key]
            if datetime.now() - cache_time < self.fundamental_cache_duration:
                self.logger.info(f"使用缓存的基本面数据: {stock_meta['display_code']}")
                return data
        
        try:
            import akshare as ak
            
            market = stock_meta['market']
            symbol = stock_meta['ak_symbol']
            display_code = stock_meta['display_code']

            # 港股/美股先做稳定降级，避免A股专属接口报错中断
            if market != 'cn_a':
                self.logger.info(f"{display_code} 为{stock_meta['market_label']}，使用简化基本面策略")
                simplified = self._get_empty_fundamental_data()
                simplified['basic_info'] = {
                    '股票代码': display_code,
                    '市场': stock_meta['market_label'],
                    '说明': '当前版本的25项财务指标接口主要面向A股，已启用简化策略'
                }
                self.fundamental_cache[cache_key] = (datetime.now(), simplified)
                return simplified

            fundamental_data = self._get_empty_fundamental_data()
            self.logger.info(f"开始获取 {display_code} 的25项综合财务指标...")
            
            # 1. 基本信息
            try:
                self.logger.info("正在获取股票基本信息...")
                stock_info = self._call_akshare_api(
                    'stock_individual_info_em',
                    retries=1,
                    retry_delay=0.3,
                    log_failure=False,
                    symbol=symbol
                )
                if stock_info is not None and not stock_info.empty:
                    info_dict = dict(zip(stock_info['item'], stock_info['value']))
                    fundamental_data['basic_info'] = info_dict
                    self.logger.info("✓ 股票基本信息获取成功")
                else:
                    fundamental_data['basic_info'] = {
                        '股票代码': display_code,
                        '市场': stock_meta['market_label'],
                        '说明': '基本信息接口暂不可用，已降级为最小信息'
                    }
                    self.logger.info("股票基本信息接口暂不可用，已降级继续")
            except Exception as e:
                self.logger.warning(f"获取基本信息失败: {e}")
                fundamental_data['basic_info'] = {
                    '股票代码': display_code,
                    '市场': stock_meta['market_label'],
                    '说明': '获取基本信息失败，已降级为最小信息'
                }
            
            # 2. 详细财务指标 - 25项核心指标
            try:
                self.logger.info("正在获取25项详细财务指标...")
                financial_indicators = {}
                
                # 获取主要财务数据
                try:
                    # 利润表数据
                    income_statement = self._call_akshare_api(
                        'stock_financial_abstract_ths',
                        retries=2,
                        symbol=symbol,
                        indicator="按报告期"
                    )
                    if income_statement is not None and not income_statement.empty:
                        latest_income = income_statement.iloc[0].to_dict()
                        financial_indicators.update(latest_income)
                except Exception as e:
                    self.logger.warning(f"获取利润表数据失败: {e}")
                
                # 获取财务分析指标
                try:
                    balance_sheet = self._call_akshare_api(
                        'stock_financial_analysis_indicator',
                        retries=2,
                        symbol=symbol
                    )
                    if balance_sheet is not None and not balance_sheet.empty:
                        latest_balance = balance_sheet.iloc[-1].to_dict()
                        financial_indicators.update(latest_balance)
                except Exception as e:
                    self.logger.warning(f"获取财务分析指标失败: {e}")
                
                # 获取现金流量表
                try:
                    cash_flow = self._call_akshare_api(
                        [
                            'stock_cash_flow_sheet_by_report_em',
                            'stock_cash_flow_sheet_by_quarterly_em',
                            'stock_cash_flow_sheet_by_yearly_em'
                        ],
                        retries=2,
                        symbol=symbol
                    )
                    if cash_flow is not None and not cash_flow.empty:
                        latest_cash = cash_flow.iloc[-1].to_dict()
                        financial_indicators.update(latest_cash)
                except Exception as e:
                    self.logger.warning(f"获取现金流量表失败: {e}")
                
                # 计算25项核心财务指标
                core_indicators = self._calculate_core_financial_indicators(financial_indicators)
                fundamental_data['financial_indicators'] = core_indicators
                
                self.logger.info(f"✓ 获取到 {len(core_indicators)} 项财务指标")
                
            except Exception as e:
                self.logger.warning(f"获取财务指标失败: {e}")
                fundamental_data['financial_indicators'] = {}
            
            # 3. 估值指标
            try:
                self.logger.info("正在获取估值指标...")
                valuation_data = self._call_akshare_api('stock_a_indicator_lg', retries=2, symbol=symbol)
                if valuation_data is not None and not valuation_data.empty:
                    latest_valuation = valuation_data.iloc[-1].to_dict()
                    # 清理估值数据中的NaN值
                    cleaned_valuation = {}
                    for key, value in latest_valuation.items():
                        if pd.isna(value) or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
                            cleaned_valuation[key] = None
                        else:
                            cleaned_valuation[key] = value
                    fundamental_data['valuation'] = cleaned_valuation
                    self.logger.info("✓ 估值指标获取成功")
                else:
                    fundamental_data['valuation'] = {}
            except Exception as e:
                self.logger.warning(f"获取估值指标失败: {e}")
                fundamental_data['valuation'] = {}
            
            # 4. 业绩预告和业绩快报
            try:
                self.logger.info("正在获取业绩预告...")
                performance_forecast = self._call_akshare_api(
                    'stock_yjbb_em',
                    retries=2,
                    date=datetime.now().strftime('%Y%m%d')
                )
                if performance_forecast is None or performance_forecast.empty:
                    performance_forecast = self._call_akshare_api('stock_yjbb_em', retries=1)

                performance_forecast = self._filter_dataframe_by_symbol(performance_forecast, symbol)
                if performance_forecast is not None and not performance_forecast.empty:
                    fundamental_data['performance_forecast'] = performance_forecast.head(10).to_dict('records')
                    self.logger.info("✓ 业绩预告获取成功")
                else:
                    fundamental_data['performance_forecast'] = []
            except Exception as e:
                self.logger.warning(f"获取业绩预告失败: {e}")
                fundamental_data['performance_forecast'] = []
            
            # 5. 分红配股信息
            try:
                self.logger.info("正在获取分红配股信息...")
                dividend_info = self._call_akshare_api(
                    ['stock_fhps_detail_em', 'stock_fhps_detail_ths', 'stock_dividend_cninfo'],
                    retries=2,
                    symbol=symbol
                )
                if dividend_info is None or dividend_info.empty:
                    dividend_info = self._call_akshare_api('stock_fhps_em', retries=1, date=datetime.now().strftime('%Y1231'))
                    dividend_info = self._filter_dataframe_by_symbol(dividend_info, symbol)

                if dividend_info is not None and not dividend_info.empty:
                    fundamental_data['dividend_info'] = dividend_info.head(10).to_dict('records')
                    self.logger.info("✓ 分红配股信息获取成功")
                else:
                    fundamental_data['dividend_info'] = []
            except Exception as e:
                self.logger.warning(f"获取分红配股信息失败: {e}")
                fundamental_data['dividend_info'] = []
            
            # 6. 行业分析
            try:
                self.logger.info("正在获取行业分析数据...")
                industry_analysis = self._get_industry_analysis(symbol)
                fundamental_data['industry_analysis'] = industry_analysis
                self.logger.info("✓ 行业分析数据获取成功")
            except Exception as e:
                self.logger.warning(f"获取行业分析失败: {e}")
                fundamental_data['industry_analysis'] = {}
            
            # 缓存数据
            self.fundamental_cache[cache_key] = (datetime.now(), fundamental_data)
            self.logger.info(f"✓ {display_code} 综合基本面数据获取完成并已缓存")
            
            return fundamental_data
            
        except Exception as e:
            self.logger.error(f"获取综合基本面数据失败: {str(e)}")
            return self._get_empty_fundamental_data()

    def _calculate_core_financial_indicators(self, raw_data):
        """计算25项核心财务指标（修正版本）"""
        try:
            indicators = {}
            
            # 从原始数据中安全获取数值
            def safe_get(key, default=0):
                value = raw_data.get(key, default)
                try:
                    if value is None or value == '' or str(value).lower() in ['nan', 'none', '--']:
                        return default
                    num_value = float(value)
                    # 检查是否为NaN或无穷大
                    if math.isnan(num_value) or math.isinf(num_value):
                        return default
                    return num_value
                except (ValueError, TypeError):
                    return default
            
            # 1-5: 盈利能力指标
            indicators['净利润率'] = safe_get('净利润率')
            indicators['净资产收益率'] = safe_get('净资产收益率')
            indicators['总资产收益率'] = safe_get('总资产收益率')
            indicators['毛利率'] = safe_get('毛利率')
            indicators['营业利润率'] = safe_get('营业利润率')
            
            # 6-10: 偿债能力指标
            indicators['流动比率'] = safe_get('流动比率')
            indicators['速动比率'] = safe_get('速动比率')
            indicators['资产负债率'] = safe_get('资产负债率')
            indicators['产权比率'] = safe_get('产权比率')
            indicators['利息保障倍数'] = safe_get('利息保障倍数')
            
            # 11-15: 营运能力指标
            indicators['总资产周转率'] = safe_get('总资产周转率')
            indicators['存货周转率'] = safe_get('存货周转率')
            indicators['应收账款周转率'] = safe_get('应收账款周转率')
            indicators['流动资产周转率'] = safe_get('流动资产周转率')
            indicators['固定资产周转率'] = safe_get('固定资产周转率')
            
            # 16-20: 发展能力指标
            indicators['营收同比增长率'] = safe_get('营收同比增长率')
            indicators['净利润同比增长率'] = safe_get('净利润同比增长率')
            indicators['总资产增长率'] = safe_get('总资产增长率')
            indicators['净资产增长率'] = safe_get('净资产增长率')
            indicators['经营现金流增长率'] = safe_get('经营现金流增长率')
            
            # 21-25: 市场表现指标
            indicators['市盈率'] = safe_get('市盈率')
            indicators['市净率'] = safe_get('市净率')
            indicators['市销率'] = safe_get('市销率')
            indicators['PEG比率'] = safe_get('PEG比率')
            indicators['股息收益率'] = safe_get('股息收益率')
            
            # 计算一些衍生指标
            try:
                # 如果有基础数据，计算一些关键比率
                revenue = safe_get('营业收入')
                net_income = safe_get('净利润')
                total_assets = safe_get('总资产')
                shareholders_equity = safe_get('股东权益')
                
                if revenue > 0 and net_income > 0:
                    if indicators['净利润率'] == 0:
                        indicators['净利润率'] = (net_income / revenue) * 100
                
                if total_assets > 0 and net_income > 0:
                    if indicators['总资产收益率'] == 0:
                        indicators['总资产收益率'] = (net_income / total_assets) * 100
                
                if shareholders_equity > 0 and net_income > 0:
                    if indicators['净资产收益率'] == 0:
                        indicators['净资产收益率'] = (net_income / shareholders_equity) * 100
                        
            except Exception as e:
                self.logger.warning(f"计算衍生指标失败: {e}")
            
            # 过滤掉无效的指标
            valid_indicators = {k: v for k, v in indicators.items() if v not in [0, None, 'nan']}
            
            self.logger.info(f"✓ 成功计算 {len(valid_indicators)} 项有效财务指标")
            return valid_indicators
            
        except Exception as e:
            self.logger.error(f"计算核心财务指标失败: {e}")
            return {}

    def _get_industry_analysis(self, stock_code):
        """获取行业分析数据"""
        try:
            industry_data = {}
            stock_code = str(stock_code or '').strip()
            
            # 获取行业信息
            try:
                industry_info = self._call_akshare_api('stock_board_industry_name_em', retries=1)
                if industry_info is not None and not industry_info.empty:
                    stock_industry = industry_info[
                        industry_info.iloc[:, 0].astype(str).str.contains(stock_code, na=False)
                    ]
                    if not stock_industry.empty:
                        industry_data['industry_info'] = stock_industry.iloc[0].to_dict()
                    else:
                        industry_data['industry_info'] = {}
                else:
                    industry_data['industry_info'] = {}
            except Exception as e:
                self.logger.warning(f"获取行业信息失败: {e}")
                industry_data['industry_info'] = {}
            
            # 获取行业排名
            try:
                hot_symbol = self._convert_to_hot_rank_symbol(stock_code)
                industry_rank = self._call_akshare_api(
                    ['stock_hot_rank_latest_em', 'stock_hot_rank_detail_em'],
                    retries=1,
                    symbol=hot_symbol
                )
                if industry_rank is not None and not industry_rank.empty:
                    industry_data['industry_rank'] = industry_rank.head(1).iloc[0].to_dict()
                else:
                    industry_data['industry_rank'] = {}
            except Exception as e:
                self.logger.warning(f"获取行业排名失败: {e}")
                industry_data['industry_rank'] = {}
            
            return industry_data
            
        except Exception as e:
            self.logger.warning(f"行业分析失败: {e}")
            return {}

    def get_comprehensive_news_data(self, stock_code, days=15):
        """获取综合新闻数据（修正版本）"""
        stock_meta = self._normalize_stock_code(stock_code)
        cache_key = f"{stock_meta['market']}:{stock_meta['ak_symbol']}:{days}"
        if cache_key in self.news_cache:
            cache_time, data = self.news_cache[cache_key]
            if datetime.now() - cache_time < self.news_cache_duration:
                self.logger.info(f"使用缓存的新闻数据: {stock_meta['display_code']}")
                return data
        
        self.logger.info(
            f"开始获取 {stock_meta['display_code']}({stock_meta['market_label']}) 的综合新闻数据（最近{days}天）..."
        )
        
        try:
            import akshare as ak
            
            stock_name = self.get_stock_name(stock_code)
            symbol = stock_meta['ak_symbol']
            market = stock_meta['market']
            max_news_count = max(10, int(self.analysis_params.get('max_news_count', 100)))
            company_limit = min(max_news_count, 60)
            announcement_limit = min(max(10, max_news_count // 2), 40)
            report_limit = min(max(8, max_news_count // 3), 30)

            all_news_data = {
                'stock_code': stock_meta['display_code'],
                'stock_name': stock_name,
                'company_news': [],
                'announcements': [],
                'research_reports': [],
                'industry_news': [],
                'market_sentiment': {},
                'news_summary': {},
                'market': stock_meta['market_label']
            }
            
            # 1. 公司新闻
            try:
                self.logger.info("正在获取公司新闻...")
                company_news = ak.stock_news_em(symbol=symbol)
                if not company_news.empty:
                    processed_news = []
                    for _, row in company_news.head(company_limit).iterrows():
                        news_item = {
                            'title': str(row.get(row.index[0], '')),
                            'content': str(row.get(row.index[1], '')) if len(row.index) > 1 else '',
                            'date': str(row.get(row.index[2], '')) if len(row.index) > 2 else datetime.now().strftime('%Y-%m-%d'),
                            'source': 'eastmoney',
                            'url': str(row.get(row.index[3], '')) if len(row.index) > 3 else '',
                            'relevance_score': 1.0
                        }
                        processed_news.append(news_item)
                    
                    all_news_data['company_news'] = processed_news
                    self.logger.info(f"✓ 获取公司新闻 {len(processed_news)} 条")
            except Exception as e:
                self.logger.warning(f"获取公司新闻失败: {e}")

            if not all_news_data['company_news']:
                self.logger.info("公司新闻为空，尝试兜底新闻源...")
                fallback_news = self._get_market_news_fallback(
                    stock_meta=stock_meta,
                    stock_name=stock_name,
                    max_items=company_limit
                )
                if fallback_news:
                    all_news_data['company_news'] = fallback_news
                    self.logger.info(f"✓ 兜底新闻源获取成功 {len(fallback_news)} 条")
            
            # 2. 公司公告
            if market == 'cn_a':
                try:
                    self.logger.info("正在获取公司公告...")
                    announcements = self._call_akshare_api(
                        ['stock_zh_a_alerts_cls'],
                        retries=2,
                        symbol=symbol,
                        date=datetime.now().strftime('%Y%m%d')
                    )
                    if announcements is None or announcements.empty:
                        announcements = self._call_akshare_api('stock_notice_report', retries=1, symbol="全部")

                    announcements = self._filter_dataframe_by_symbol(announcements, symbol)
                    if announcements is not None and not announcements.empty:
                        processed_announcements = []
                        for _, row in announcements.head(announcement_limit).iterrows():
                            announcement = {
                                'title': str(row.get(row.index[0], '')),
                                'content': str(row.get(row.index[1], '')) if len(row.index) > 1 else '',
                                'date': str(row.get(row.index[2], '')) if len(row.index) > 2 else datetime.now().strftime('%Y-%m-%d'),
                                'type': str(row.get(row.index[3], '')) if len(row.index) > 3 else '公告',
                                'relevance_score': 1.0
                            }
                            processed_announcements.append(announcement)
                        
                        all_news_data['announcements'] = processed_announcements
                        self.logger.info(f"✓ 获取公司公告 {len(processed_announcements)} 条")
                except Exception as e:
                    self.logger.warning(f"获取公司公告失败: {e}")
            else:
                self.logger.info(f"{stock_meta['market_label']}暂不使用A股公告接口，跳过公告抓取")
            
            # 3. 研究报告
            if market == 'cn_a':
                try:
                    self.logger.info("正在获取研究报告...")
                    research_reports = self._call_akshare_api(
                        'stock_research_report_em',
                        retries=2,
                        symbol=symbol
                    )
                    if research_reports is not None and not research_reports.empty:
                        processed_reports = []
                        for _, row in research_reports.head(report_limit).iterrows():
                            report = {
                                'title': str(row.get(row.index[0], '')),
                                'institution': str(row.get(row.index[1], '')) if len(row.index) > 1 else '',
                                'rating': str(row.get(row.index[2], '')) if len(row.index) > 2 else '',
                                'target_price': str(row.get(row.index[3], '')) if len(row.index) > 3 else '',
                                'date': str(row.get(row.index[4], '')) if len(row.index) > 4 else datetime.now().strftime('%Y-%m-%d'),
                                'relevance_score': 0.9
                            }
                            processed_reports.append(report)
                        
                        all_news_data['research_reports'] = processed_reports
                        self.logger.info(f"✓ 获取研究报告 {len(processed_reports)} 条")
                except Exception as e:
                    self.logger.warning(f"获取研究报告失败: {e}")
            else:
                self.logger.info(f"{stock_meta['market_label']}暂不使用A股研报接口，跳过研报抓取")
            
            # 4. 行业新闻
            try:
                self.logger.info("正在获取行业新闻...")
                industry_news = self._get_comprehensive_industry_news(stock_code, days)
                all_news_data['industry_news'] = industry_news
                self.logger.info(f"✓ 获取行业新闻 {len(industry_news)} 条")
            except Exception as e:
                self.logger.warning(f"获取行业新闻失败: {e}")
            
            # 5. 新闻摘要统计
            try:
                total_news = (len(all_news_data['company_news']) + 
                            len(all_news_data['announcements']) + 
                            len(all_news_data['research_reports']) + 
                            len(all_news_data['industry_news']))
                
                all_news_data['news_summary'] = {
                    'stock_name': stock_name,
                    'market': stock_meta['market_label'],
                    'total_news_count': total_news,
                    'company_news_count': len(all_news_data['company_news']),
                    'announcements_count': len(all_news_data['announcements']),
                    'research_reports_count': len(all_news_data['research_reports']),
                    'industry_news_count': len(all_news_data['industry_news']),
                    'data_freshness': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
            except Exception as e:
                self.logger.warning(f"生成新闻摘要失败: {e}")
            
            # 缓存数据
            self.news_cache[cache_key] = (datetime.now(), all_news_data)
            
            self.logger.info(f"✓ 综合新闻数据获取完成，总计 {all_news_data['news_summary'].get('total_news_count', 0)} 条")
            return all_news_data
            
        except Exception as e:
            self.logger.error(f"获取综合新闻数据失败: {str(e)}")
            stock_meta = self._normalize_stock_code(stock_code)
            return {
                'stock_code': stock_meta['display_code'],
                'stock_name': stock_meta['display_code'],
                'company_news': [],
                'announcements': [],
                'research_reports': [],
                'industry_news': [],
                'market_sentiment': {},
                'news_summary': {'total_news_count': 0},
                'market': stock_meta['market_label']
            }

    def _get_comprehensive_industry_news(self, stock_code, days=30):
        """获取详细的行业新闻"""
        try:
            # 这里可以根据实际需要扩展行业新闻获取逻辑
            # 目前返回一个示例结构
            industry_news = []
            
            # 可以添加更多的行业新闻源
            # 比如获取同行业其他公司的新闻
            # 获取行业政策新闻等
            
            self.logger.info(f"行业新闻获取完成，共 {len(industry_news)} 条")
            return industry_news
            
        except Exception as e:
            self.logger.warning(f"获取行业新闻失败: {e}")
            return []

    def _build_news_item(self, title, content='', date_str='', source='unknown', url='', relevance_score=0.8):
        """统一新闻结构"""
        return {
            'title': self._clip_text(title, 180),
            'content': self._clip_text(content, 500),
            'date': str(date_str or datetime.now().strftime('%Y-%m-%d')),
            'source': str(source or 'unknown'),
            'url': str(url or ''),
            'relevance_score': float(relevance_score)
        }

    def _extract_row_value(self, row_dict, candidates, default=''):
        """从DataFrame行字典中按候选字段提取值"""
        for key in candidates:
            if key in row_dict and row_dict.get(key) not in (None, ''):
                return row_dict.get(key)
        return default

    def _normalize_yahoo_symbol(self, stock_meta):
        """生成Yahoo RSS常见代码格式"""
        market = stock_meta.get('market')
        symbol = str(stock_meta.get('ak_symbol', '')).upper()

        if market == 'us':
            if re.match(r'^\d+\.[A-Z0-9\.\-]+$', symbol):
                return symbol.split('.', 1)[1]
            return symbol

        if market == 'hk':
            digits = re.sub(r'\D', '', symbol)
            if not digits:
                return ""
            # Yahoo常见格式是4位港股代码 + .HK
            return f"{digits.zfill(5)[-4:]}.HK"

        if market == 'cn_a':
            return stock_meta.get('display_code', '')

        return symbol

    def _fetch_yahoo_rss_news(self, symbol, max_items=20):
        """从Yahoo RSS获取新闻，适配港美股"""
        if not symbol:
            return []

        rss_urls = [
            f"https://finance.yahoo.com/rss/headline?s={symbol}",
            f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        ]

        for rss_url in rss_urls:
            try:
                response = requests.get(
                    rss_url,
                    timeout=12,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                response.raise_for_status()
                xml_text = response.content.decode('utf-8', errors='replace')
                root = ET.fromstring(xml_text)

                items = []
                for node in root.findall('.//item')[:max_items]:
                    title = (node.findtext('title') or '').strip()
                    description = (node.findtext('description') or '').strip()
                    pub_date = (node.findtext('pubDate') or '').strip()
                    link = (node.findtext('link') or '').strip()
                    if not title:
                        continue
                    items.append(
                        self._build_news_item(
                            title=title,
                            content=description,
                            date_str=pub_date,
                            source='yahoo_finance_rss',
                            url=link,
                            relevance_score=0.85
                        )
                    )

                if items:
                    self.logger.info(f"✓ Yahoo RSS获取新闻成功: {len(items)} 条")
                    return items
            except Exception as rss_error:
                self.logger.info(f"Yahoo RSS抓取失败({rss_url}): {rss_error}")
                continue

        return []

    def _get_market_news_fallback(self, stock_meta, stock_name, max_items=20):
        """港美股新闻抓取兜底，保证JSON模式有输入"""
        fallback_news = []
        market = stock_meta.get('market')
        display_code = str(stock_meta.get('display_code', '')).upper()
        stock_name = str(stock_name or '').strip()
        search_keywords = [display_code, stock_name]

        # 1) 通用财经新闻源，按关键词筛选
        try:
            import akshare as ak
            main_news = ak.stock_news_main_cx()
            if main_news is not None and not main_news.empty:
                filtered = []
                for _, row in main_news.head(max_items * 8).iterrows():
                    row_dict = row.to_dict() if hasattr(row, 'to_dict') else {}
                    title = str(
                        self._extract_row_value(
                            row_dict,
                            ['标题', 'title', '新闻标题', 'col_0'],
                            row.iloc[0] if len(row) > 0 else ''
                        )
                    )
                    content = str(
                        self._extract_row_value(
                            row_dict,
                            ['内容', '摘要', 'content', 'col_1'],
                            row.iloc[1] if len(row) > 1 else ''
                        )
                    )
                    date_str = str(
                        self._extract_row_value(
                            row_dict,
                            ['发布时间', '日期', 'time', 'date', 'col_2'],
                            row.iloc[2] if len(row) > 2 else ''
                        )
                    )
                    link = str(
                        self._extract_row_value(
                            row_dict,
                            ['链接', 'url', 'link', 'col_3'],
                            row.iloc[3] if len(row) > 3 else ''
                        )
                    )

                    text_for_match = f"{title} {content}".upper()
                    if any(str(k).upper() in text_for_match for k in search_keywords if k):
                        filtered.append(
                            self._build_news_item(
                                title=title,
                                content=content,
                                date_str=date_str,
                                source='akshare_stock_news_main_cx',
                                url=link,
                                relevance_score=0.75
                            )
                        )
                    if len(filtered) >= max_items:
                        break

                if filtered:
                    self.logger.info(f"✓ 兜底新闻源命中 {len(filtered)} 条")
                    fallback_news.extend(filtered)
        except Exception as fallback_error:
            self.logger.info(f"兜底财经新闻源不可用: {fallback_error}")

        if len(fallback_news) >= max_items:
            return fallback_news[:max_items]

        # A股也尝试Yahoo RSS（部分中概或双重上市有覆盖）
        if market == 'cn_a' and not fallback_news:
            yahoo_symbol = str(stock_meta.get('display_code', ''))
            yahoo_news = self._fetch_yahoo_rss_news(
                symbol=yahoo_symbol,
                max_items=max_items
            )
            fallback_news.extend(yahoo_news)

        # 2) 美股/港股优先使用Yahoo RSS补齐
        if market in ('us', 'hk'):
            yahoo_symbol = self._normalize_yahoo_symbol(stock_meta)
            yahoo_news = self._fetch_yahoo_rss_news(
                symbol=yahoo_symbol,
                max_items=max_items - len(fallback_news)
            )
            fallback_news.extend(yahoo_news)

        return fallback_news[:max_items]

    def _get_provider_model(self, provider):
        """获取指定provider对应模型，缺省回退到主模型"""
        ai_config = self.config.get('ai', {})
        models = ai_config.get('models', {})
        provider = str(provider or '').strip().lower()
        provider_alias = {
            'claude': 'anthropic',
            'silicon-flow': 'siliconflow'
        }
        provider = provider_alias.get(provider, provider)
        if provider in models and models.get(provider):
            return models.get(provider)

        preferred_provider = ai_config.get('model_preference', 'openai')
        if preferred_provider in models and models.get(preferred_provider):
            return models.get(preferred_provider)

        return "gpt-4o-mini"

    def _infer_provider_from_model(self, model_name):
        """根据模型名称推断provider，避免provider留空时误用主API"""
        model_text = str(model_name or '').strip()
        if not model_text:
            return ""

        model_lower = model_text.lower()
        ai_config = self.config.get('ai', {})
        models = ai_config.get('models', {})

        provider_alias = {
            'claude': 'anthropic',
            'silicon-flow': 'siliconflow'
        }

        # 1) 优先精确匹配配置里的provider->model映射
        matched_providers = []
        for provider_name, configured_model in models.items():
            normalized_provider = provider_alias.get(
                str(provider_name or '').strip().lower(),
                str(provider_name or '').strip().lower()
            )
            if not normalized_provider:
                continue
            if str(configured_model or '').strip().lower() == model_lower:
                matched_providers.append(normalized_provider)

        for provider_name in matched_providers:
            if self.api_keys.get(provider_name):
                return provider_name
        if matched_providers:
            return matched_providers[0]

        # 2) 常见SiliconFlow模型前缀启发式
        siliconflow_prefixes = (
            'qwen/',
            'deepseek/',
            'internlm/',
            'meta-llama/',
            'llama-',
            'baai/',
            'moonshotai/',
            'thudm/'
        )
        if model_lower.startswith(siliconflow_prefixes):
            return 'siliconflow'

        # 3) OpenAI常见模型前缀
        openai_prefixes = ('gpt-', 'o1', 'o3')
        if model_lower.startswith(openai_prefixes):
            return 'openai'

        return ""

    def _resolve_json_mode_target(self):
        """解析JSON模式使用的provider/model，默认复用结论模型"""
        ai_config = self.config.get('ai', {})
        json_mode = ai_config.get('json_mode', {})
        preferred_provider = str(ai_config.get('model_preference', 'openai')).strip().lower()
        raw_provider = str(json_mode.get('provider') or '').strip()
        explicit_provider = bool(raw_provider)
        provider = str(raw_provider or preferred_provider).strip().lower()
        provider_alias = {
            'claude': 'anthropic',
            'silicon-flow': 'siliconflow'
        }
        provider = provider_alias.get(provider, provider)

        explicit_model = str(json_mode.get('model') or '').strip()
        if explicit_model and not explicit_provider:
            inferred_provider = self._infer_provider_from_model(explicit_model)
            if inferred_provider:
                provider = inferred_provider
                self.logger.info(
                    f"JSON模式provider未显式配置，已按模型自动识别为: {provider}"
                )

        model = str(explicit_model or self._get_provider_model(provider)).strip()
        if not model:
            model = self._get_provider_model(preferred_provider)

        return provider, model

    def _safe_parse_json_text(self, text):
        """安全解析模型返回的JSON文本"""
        if not text:
            return None

        content = str(text).strip()
        if not content:
            return None

        # 处理```json ...```代码块
        fenced_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content, re.IGNORECASE)
        if fenced_match:
            content = fenced_match.group(1).strip()

        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # 尝试提取最外层JSON对象
        obj_match = re.search(r'\{[\s\S]*\}', content)
        if obj_match:
            try:
                parsed = json.loads(obj_match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return None

        return None

    def _clip_text(self, text, max_len=180):
        """裁剪文本长度，避免提示词过大"""
        content = str(text or '').strip()
        if len(content) <= max_len:
            return content
        return content[:max_len] + "..."

    def _collect_news_for_json_mode(self, comprehensive_news_data, max_items=30):
        """整理新闻为JSON模式输入格式"""
        items = []

        for news in comprehensive_news_data.get('company_news', []):
            items.append({
                'type': 'company_news',
                'title': self._clip_text(news.get('title', ''), 120),
                'content': self._clip_text(news.get('content', ''), 240),
                'date': str(news.get('date', '')),
                'source': str(news.get('source', ''))
            })

        for announcement in comprehensive_news_data.get('announcements', []):
            items.append({
                'type': 'announcement',
                'title': self._clip_text(announcement.get('title', ''), 120),
                'content': self._clip_text(announcement.get('content', ''), 220),
                'date': str(announcement.get('date', '')),
                'source': str(announcement.get('type', '公告'))
            })

        for report in comprehensive_news_data.get('research_reports', []):
            report_title = report.get('title', '')
            report_rating = report.get('rating', '')
            items.append({
                'type': 'research_report',
                'title': self._clip_text(report_title, 120),
                'content': self._clip_text(f"评级:{report_rating} 机构:{report.get('institution', '')}", 200),
                'date': str(report.get('date', '')),
                'source': str(report.get('institution', ''))
            })

        for industry_news in comprehensive_news_data.get('industry_news', []):
            items.append({
                'type': 'industry_news',
                'title': self._clip_text(industry_news.get('title', ''), 120),
                'content': self._clip_text(industry_news.get('content', ''), 220),
                'date': str(industry_news.get('date', '')),
                'source': str(industry_news.get('source', ''))
            })

        return items[:max_items]

    def _normalize_string_list(self, value, max_items=8, item_max_len=80):
        """将模型输出统一为字符串列表"""
        if value is None:
            return []

        values = value if isinstance(value, list) else [value]
        normalized = []
        for item in values:
            text = str(item).strip()
            if text:
                normalized.append(self._clip_text(text, item_max_len))
            if len(normalized) >= max_items:
                break
        return normalized

    def _build_compressed_news_context(self, sentiment_analysis):
        """将原始新闻压缩为主模型可消费摘要，减少提示词长度与噪声"""
        try:
            if not isinstance(sentiment_analysis, dict):
                return {
                    'summary_text': '暂无可用新闻摘要。',
                    'raw_text_length': 0,
                    'compressed_text_length': 9,
                    'compression_ratio': 1.0,
                    'source_counts': {}
                }

            news_summary = sentiment_analysis.get('news_summary', {})
            company_news = sentiment_analysis.get('company_news', [])
            announcements = sentiment_analysis.get('announcements', [])
            research_reports = sentiment_analysis.get('research_reports', [])
            industry_news = sentiment_analysis.get('industry_news', [])

            company_news = company_news if isinstance(company_news, list) else []
            announcements = announcements if isinstance(announcements, list) else []
            research_reports = research_reports if isinstance(research_reports, list) else []
            industry_news = industry_news if isinstance(industry_news, list) else []

            source_counts = {
                'company_news': len(company_news),
                'announcements': len(announcements),
                'research_reports': len(research_reports),
                'industry_news': len(industry_news)
            }

            total_news_count = (
                int(news_summary.get('total_news_count', 0))
                if isinstance(news_summary, dict) else 0
            )
            if total_news_count <= 0:
                total_news_count = sum(source_counts.values())

            max_items = max(4, int(self.analysis_params.get('main_prompt_news_max_items', 12) or 12))
            max_chars = max(400, int(self.analysis_params.get('main_prompt_news_max_chars', 1200) or 1200))

            raw_fragments = []
            for item in company_news:
                raw_fragments.append(str(item.get('title', '')))
                raw_fragments.append(str(item.get('content', '')))
            for item in announcements:
                raw_fragments.append(str(item.get('title', '')))
                raw_fragments.append(str(item.get('content', '')))
            for item in research_reports:
                raw_fragments.append(str(item.get('title', '')))
                raw_fragments.append(str(item.get('rating', '')))
                raw_fragments.append(str(item.get('institution', '')))
            for item in industry_news:
                raw_fragments.append(str(item.get('title', '')))
                raw_fragments.append(str(item.get('content', '')))

            if sentiment_analysis.get('llm_json_mode_used', False):
                raw_fragments.append(str(sentiment_analysis.get('context_summary', '')))
                for key in ('key_points', 'risk_points', 'opportunity_points', 'catalysts'):
                    values = sentiment_analysis.get(key, [])
                    if isinstance(values, list):
                        raw_fragments.extend([str(v) for v in values])
                    elif values:
                        raw_fragments.append(str(values))

            raw_text_length = sum(len(text) for text in raw_fragments if text)

            lines = [
                (
                    f"新闻覆盖: 总计{total_news_count}条，"
                    f"公司新闻{source_counts['company_news']}条，"
                    f"公告{source_counts['announcements']}条，"
                    f"研报{source_counts['research_reports']}条，"
                    f"行业{source_counts['industry_news']}条。"
                )
            ]

            llm_json_mode_used = bool(sentiment_analysis.get('llm_json_mode_used', False))
            if llm_json_mode_used:
                context_summary = self._clip_text(sentiment_analysis.get('context_summary', ''), 180)
                key_points = self._normalize_string_list(
                    sentiment_analysis.get('key_points', []),
                    max_items=4,
                    item_max_len=72
                )
                risk_points = self._normalize_string_list(
                    sentiment_analysis.get('risk_points', []),
                    max_items=3,
                    item_max_len=72
                )
                opportunity_points = self._normalize_string_list(
                    sentiment_analysis.get('opportunity_points', []),
                    max_items=3,
                    item_max_len=72
                )
                catalysts = self._normalize_string_list(
                    sentiment_analysis.get('catalysts', []),
                    max_items=3,
                    item_max_len=72
                )

                if context_summary:
                    lines.append(f"上下文总结: {context_summary}")
                if key_points:
                    lines.append(f"关键要点: {'；'.join(key_points)}")
                if risk_points:
                    lines.append(f"主要风险: {'；'.join(risk_points)}")
                if opportunity_points:
                    lines.append(f"主要机会: {'；'.join(opportunity_points)}")
                if catalysts:
                    lines.append(f"潜在催化: {'；'.join(catalysts)}")

            selected_headlines = []
            seen = set()

            def append_headline(prefix, title):
                title_text = self._clip_text(title, 72)
                if not title_text:
                    return
                normalized = re.sub(r'[\W_]+', '', title_text).lower()
                if not normalized or normalized in seen:
                    return
                seen.add(normalized)
                selected_headlines.append(f"- {prefix}{title_text}")

            for item in company_news[:max_items]:
                append_headline('', str(item.get('title', '')))
            for item in announcements[:max_items]:
                append_headline('[公告] ', str(item.get('title', '')))
            for item in research_reports[:max_items]:
                institution = str(item.get('institution', '')).strip()
                rating = str(item.get('rating', '')).strip()
                title = str(item.get('title', '')).strip()
                report_prefix = '[研报] '
                if institution:
                    report_prefix += f"{institution}"
                if rating:
                    report_prefix += f"({rating})"
                report_prefix += ": " if institution or rating else ""
                append_headline(report_prefix, title)
            for item in industry_news[:max_items]:
                append_headline('[行业] ', str(item.get('title', '')))

            if selected_headlines:
                lines.append("代表性新闻:")
                lines.extend(selected_headlines[:max_items])

            summary_text = "\n".join([line for line in lines if str(line).strip()]).strip()
            if not summary_text:
                summary_text = "暂无可用新闻摘要。"
            summary_text = self._clip_text(summary_text, max_chars)

            compressed_text_length = len(summary_text)
            compression_ratio = (
                min(1.0, round(compressed_text_length / raw_text_length, 4))
                if raw_text_length > 0 else 1.0
            )

            return {
                'summary_text': summary_text,
                'raw_text_length': raw_text_length,
                'compressed_text_length': compressed_text_length,
                'compression_ratio': compression_ratio,
                'source_counts': source_counts,
                'total_news_count': total_news_count,
                'selected_headlines': selected_headlines[:max_items],
                'llm_json_mode_used': llm_json_mode_used
            }
        except Exception as e:
            self.logger.warning(f"新闻压缩失败: {e}")
            return {
                'summary_text': '新闻压缩失败，降级使用基础统计信息。',
                'raw_text_length': 0,
                'compressed_text_length': 17,
                'compression_ratio': 1.0,
                'source_counts': {},
                'total_news_count': 0,
                'selected_headlines': [],
                'llm_json_mode_used': False
            }

    def _analyze_news_with_json_mode(self, comprehensive_news_data):
        """使用JSON Mode进行新闻分析和上下文总结"""
        ai_config = self.config.get('ai', {})
        json_mode_cfg = ai_config.get('json_mode', {})
        if not json_mode_cfg.get('enabled', False):
            return None

        provider, model = self._resolve_json_mode_target()
        if provider not in ('openai', 'siliconflow'):
            self.logger.warning(
                f"JSON模式暂仅支持openai/siliconflow兼容接口，当前provider={provider}，自动回退规则分析"
            )
            return None

        max_news_items = int(json_mode_cfg.get('max_news_items', 30) or 30)
        news_items = self._collect_news_for_json_mode(comprehensive_news_data, max_items=max_news_items)
        if not news_items:
            self.logger.info("JSON模式已启用，但新闻数量为0，跳过模型情绪分析")
            return None

        stock_code = comprehensive_news_data.get('stock_code', '')
        stock_name = comprehensive_news_data.get('stock_name', stock_code)
        json_temperature = float(json_mode_cfg.get('temperature', 0.2) or 0.2)
        json_max_tokens = int(json_mode_cfg.get('max_tokens', 1800) or 1800)

        prompt = f"""你是一名量化投研分析师。请基于给定新闻，输出严格JSON对象，不要输出任何额外文本。

股票信息:
- 股票代码: {stock_code}
- 股票名称: {stock_name}

新闻列表(JSON):
{json.dumps(news_items, ensure_ascii=False)}

输出JSON格式(字段不可缺失):
{{
  "overall_sentiment": -1到1之间的浮点数,
  "sentiment_trend": "非常积极/偏向积极/相对中性/偏向消极/非常消极",
  "confidence_score": 0到1之间的浮点数,
  "sentiment_by_type": {{
    "company_news": -1到1,
    "announcement": -1到1,
    "research_report": -1到1,
    "industry_news": -1到1
  }},
  "context_summary": "不超过180字的新闻上下文总结",
  "key_points": ["关键事实1", "关键事实2"],
  "risk_points": ["风险点1", "风险点2"],
  "opportunity_points": ["机会点1", "机会点2"],
  "catalysts": ["催化剂1", "催化剂2"]
}}"""

        system_prompt = (
            "你是专业二级市场研究员。仅输出合法JSON。"
            "如果证据不足，保持中性并降低confidence_score。"
        )

        response_text = self._call_openai_compatible_api(
            provider=provider,
            prompt=prompt,
            enable_streaming=False,
            stream_callback=None,
            system_prompt=system_prompt,
            model_override=model,
            max_tokens_override=json_max_tokens,
            temperature_override=json_temperature,
            require_json=True
        )

        parsed = self._safe_parse_json_text(response_text)
        tried_targets = {(provider, model)}
        if not parsed:
            fallback_provider = str(ai_config.get('model_preference', 'openai')).strip().lower()
            provider_alias = {
                'claude': 'anthropic',
                'silicon-flow': 'siliconflow'
            }
            fallback_provider = provider_alias.get(fallback_provider, fallback_provider)
            fallback_model = self._get_provider_model(fallback_provider)

            if (
                fallback_provider in ('openai', 'siliconflow')
                and (fallback_provider != provider or fallback_model != model)
            ):
                self.logger.info(
                    f"JSON模式首选模型不可用，尝试回退到结论模型: {fallback_provider}/{fallback_model}"
                )
                fallback_response_text = self._call_openai_compatible_api(
                    provider=fallback_provider,
                    prompt=prompt,
                    enable_streaming=False,
                    stream_callback=None,
                    system_prompt=system_prompt,
                    model_override=fallback_model,
                    max_tokens_override=json_max_tokens,
                    temperature_override=json_temperature,
                    require_json=True
                )
                parsed = self._safe_parse_json_text(fallback_response_text)
                tried_targets.add((fallback_provider, fallback_model))
                if parsed:
                    provider = fallback_provider
                    model = fallback_model

        # 如果首选与结论模型均不可用，再尝试另一个兼容provider
        if not parsed:
            for backup_provider in ('siliconflow', 'openai'):
                if not self.api_keys.get(backup_provider):
                    continue
                backup_model = self._get_provider_model(backup_provider)
                if (backup_provider, backup_model) in tried_targets:
                    continue

                self.logger.info(
                    f"JSON模式继续尝试兼容备用模型: {backup_provider}/{backup_model}"
                )
                backup_response_text = self._call_openai_compatible_api(
                    provider=backup_provider,
                    prompt=prompt,
                    enable_streaming=False,
                    stream_callback=None,
                    system_prompt=system_prompt,
                    model_override=backup_model,
                    max_tokens_override=json_max_tokens,
                    temperature_override=json_temperature,
                    require_json=True
                )
                parsed = self._safe_parse_json_text(backup_response_text)
                tried_targets.add((backup_provider, backup_model))
                if parsed:
                    provider = backup_provider
                    model = backup_model
                    break

        if not parsed:
            self.logger.warning("JSON模式返回无法解析为JSON，回退规则情绪分析")
            return None

        def clamp(value, low, high, default):
            try:
                num = float(value)
                return max(low, min(high, num))
            except Exception:
                return default

        overall_sentiment = clamp(parsed.get('overall_sentiment', 0.0), -1.0, 1.0, 0.0)
        confidence_score = clamp(parsed.get('confidence_score', 0.5), 0.0, 1.0, 0.5)

        trend = str(parsed.get('sentiment_trend', '')).strip()
        if not trend:
            if overall_sentiment > 0.3:
                trend = '非常积极'
            elif overall_sentiment > 0.1:
                trend = '偏向积极'
            elif overall_sentiment > -0.1:
                trend = '相对中性'
            elif overall_sentiment > -0.3:
                trend = '偏向消极'
            else:
                trend = '非常消极'

        sentiment_by_type = {}
        raw_sentiment_by_type = parsed.get('sentiment_by_type', {})
        if isinstance(raw_sentiment_by_type, dict):
            for key, value in raw_sentiment_by_type.items():
                sentiment_by_type[str(key)] = clamp(value, -1.0, 1.0, 0.0)

        if not sentiment_by_type:
            sentiment_by_type = {
                'company_news': overall_sentiment,
                'announcement': overall_sentiment,
                'research_report': overall_sentiment,
                'industry_news': overall_sentiment
            }

        positives = len([v for v in sentiment_by_type.values() if v > 0])
        negatives = len([v for v in sentiment_by_type.values() if v < 0])
        total_types = max(len(sentiment_by_type), 1)

        type_distribution = {}
        for news_item in news_items:
            news_type = news_item.get('type', 'unknown')
            type_distribution[news_type] = type_distribution.get(news_type, 0) + 1

        return {
            'overall_sentiment': overall_sentiment,
            'sentiment_by_type': sentiment_by_type,
            'sentiment_trend': trend,
            'confidence_score': confidence_score,
            'total_analyzed': len(news_items),
            'type_distribution': type_distribution,
            'positive_ratio': positives / total_types,
            'negative_ratio': negatives / total_types,
            'context_summary': self._clip_text(parsed.get('context_summary', ''), 220),
            'key_points': self._normalize_string_list(parsed.get('key_points', []), max_items=8, item_max_len=90),
            'risk_points': self._normalize_string_list(parsed.get('risk_points', []), max_items=8, item_max_len=90),
            'opportunity_points': self._normalize_string_list(parsed.get('opportunity_points', []), max_items=8, item_max_len=90),
            'catalysts': self._normalize_string_list(parsed.get('catalysts', []), max_items=8, item_max_len=90),
            'llm_json_mode_used': True,
            'json_model_provider': provider,
            'json_model_name': model
        }

    def calculate_advanced_sentiment_analysis(self, comprehensive_news_data):
        """计算高级情绪分析（修正版本）"""
        self.logger.info("开始高级情绪分析...")
        
        try:
            json_mode_result = self._analyze_news_with_json_mode(comprehensive_news_data)
            if json_mode_result:
                self.logger.info(
                    f"✓ JSON模式新闻分析完成: {json_mode_result.get('sentiment_trend', '相对中性')}"
                )
                return json_mode_result

            # 准备所有新闻文本
            all_texts = []
            
            # 收集所有新闻文本
            for news in comprehensive_news_data.get('company_news', []):
                text = f"{news.get('title', '')} {news.get('content', '')}"
                all_texts.append({'text': text, 'type': 'company_news', 'weight': 1.0})
            
            for announcement in comprehensive_news_data.get('announcements', []):
                text = f"{announcement.get('title', '')} {announcement.get('content', '')}"
                all_texts.append({'text': text, 'type': 'announcement', 'weight': 1.2})  # 公告权重更高
            
            for report in comprehensive_news_data.get('research_reports', []):
                text = f"{report.get('title', '')} {report.get('rating', '')}"
                all_texts.append({'text': text, 'type': 'research_report', 'weight': 0.9})
            
            for news in comprehensive_news_data.get('industry_news', []):
                text = f"{news.get('title', '')} {news.get('content', '')}"
                all_texts.append({'text': text, 'type': 'industry_news', 'weight': 0.7})
            
            if not all_texts:
                return {
                    'overall_sentiment': 0.0,
                    'sentiment_by_type': {},
                    'sentiment_trend': '中性',
                    'confidence_score': 0.0,
                    'total_analyzed': 0,
                    'llm_json_mode_used': False
                }
            
            # 扩展的情绪词典
            positive_words = {
                '上涨', '涨停', '利好', '突破', '增长', '盈利', '收益', '回升', '强势', '看好',
                '买入', '推荐', '优秀', '领先', '创新', '发展', '机会', '潜力', '稳定', '改善',
                '提升', '超预期', '积极', '乐观', '向好', '受益', '龙头', '热点', '爆发', '翻倍',
                '业绩', '增收', '扩张', '合作', '签约', '中标', '获得', '成功', '完成', '达成'
            }
            
            negative_words = {
                '下跌', '跌停', '利空', '破位', '下滑', '亏损', '风险', '回调', '弱势', '看空',
                '卖出', '减持', '较差', '落后', '滞后', '困难', '危机', '担忧', '悲观', '恶化',
                '下降', '低于预期', '消极', '压力', '套牢', '被套', '暴跌', '崩盘', '踩雷', '退市',
                '违规', '处罚', '调查', '停牌', '亏损', '债务', '违约', '诉讼', '纠纷', '问题'
            }
            
            # 分析每类新闻的情绪
            sentiment_by_type = {}
            overall_scores = []
            
            for text_data in all_texts:
                try:
                    text = text_data['text']
                    text_type = text_data['type']
                    weight = text_data['weight']
                    
                    if not text.strip():
                        continue
                    
                    positive_count = sum(1 for word in positive_words if word in text)
                    negative_count = sum(1 for word in negative_words if word in text)
                    
                    # 计算情绪得分
                    total_sentiment_words = positive_count + negative_count
                    if total_sentiment_words > 0:
                        sentiment_score = (positive_count - negative_count) / total_sentiment_words
                    else:
                        sentiment_score = 0.0
                    
                    # 应用权重
                    weighted_score = sentiment_score * weight
                    overall_scores.append(weighted_score)
                    
                    # 按类型统计
                    if text_type not in sentiment_by_type:
                        sentiment_by_type[text_type] = []
                    sentiment_by_type[text_type].append(weighted_score)
                    
                except Exception as e:
                    continue
            
            # 计算总体情绪
            overall_sentiment = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
            
            # 计算各类型平均情绪
            avg_sentiment_by_type = {}
            for text_type, scores in sentiment_by_type.items():
                avg_sentiment_by_type[text_type] = sum(scores) / len(scores) if scores else 0.0
            
            # 判断情绪趋势
            if overall_sentiment > 0.3:
                sentiment_trend = '非常积极'
            elif overall_sentiment > 0.1:
                sentiment_trend = '偏向积极'
            elif overall_sentiment > -0.1:
                sentiment_trend = '相对中性'
            elif overall_sentiment > -0.3:
                sentiment_trend = '偏向消极'
            else:
                sentiment_trend = '非常消极'
            
            # 计算置信度
            confidence_score = min(len(all_texts) / 50, 1.0)  # 基于新闻数量的置信度
            
            result = {
                'overall_sentiment': overall_sentiment,
                'sentiment_by_type': avg_sentiment_by_type,
                'sentiment_trend': sentiment_trend,
                'confidence_score': confidence_score,
                'total_analyzed': len(all_texts),
                'type_distribution': {k: len(v) for k, v in sentiment_by_type.items()},
                'positive_ratio': len([s for s in overall_scores if s > 0]) / len(overall_scores) if overall_scores else 0,
                'negative_ratio': len([s for s in overall_scores if s < 0]) / len(overall_scores) if overall_scores else 0,
                'llm_json_mode_used': False
            }
            
            self.logger.info(f"✓ 高级情绪分析完成: {sentiment_trend} (得分: {overall_sentiment:.3f})")
            return result
            
        except Exception as e:
            self.logger.error(f"高级情绪分析失败: {e}")
            return {
                'overall_sentiment': 0.0,
                'sentiment_by_type': {},
                'sentiment_trend': '分析失败',
                'confidence_score': 0.0,
                'total_analyzed': 0,
                'llm_json_mode_used': False
            }

    def calculate_technical_indicators(self, price_data):
        """计算技术指标（修正版本）"""
        try:
            if price_data.empty:
                return self._get_default_technical_analysis()
            
            technical_analysis = {}
            
            # 安全的数值处理函数
            def safe_float(value, default=50.0):
                try:
                    if pd.isna(value):
                        return default
                    num_value = float(value)
                    if math.isnan(num_value) or math.isinf(num_value):
                        return default
                    return num_value
                except (ValueError, TypeError):
                    return default
            
            # 移动平均线
            try:
                price_data['ma5'] = price_data['close'].rolling(window=5, min_periods=1).mean()
                price_data['ma10'] = price_data['close'].rolling(window=10, min_periods=1).mean()
                price_data['ma20'] = price_data['close'].rolling(window=20, min_periods=1).mean()
                price_data['ma60'] = price_data['close'].rolling(window=60, min_periods=1).mean()
                
                latest_price = safe_float(price_data['close'].iloc[-1])
                ma5 = safe_float(price_data['ma5'].iloc[-1], latest_price)
                ma10 = safe_float(price_data['ma10'].iloc[-1], latest_price)
                ma20 = safe_float(price_data['ma20'].iloc[-1], latest_price)
                
                if latest_price > ma5 > ma10 > ma20:
                    technical_analysis['ma_trend'] = '多头排列'
                elif latest_price < ma5 < ma10 < ma20:
                    technical_analysis['ma_trend'] = '空头排列'
                else:
                    technical_analysis['ma_trend'] = '震荡整理'
                
            except Exception as e:
                technical_analysis['ma_trend'] = '计算失败'
            
            # RSI指标
            try:
                def calculate_rsi(prices, window=14):
                    delta = prices.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=window, min_periods=1).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=window, min_periods=1).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    return rsi
                
                rsi_series = calculate_rsi(price_data['close'])
                technical_analysis['rsi'] = safe_float(rsi_series.iloc[-1], 50.0)
                
            except Exception as e:
                technical_analysis['rsi'] = 50.0
            
            # MACD指标
            try:
                ema12 = price_data['close'].ewm(span=12, min_periods=1).mean()
                ema26 = price_data['close'].ewm(span=26, min_periods=1).mean()
                macd_line = ema12 - ema26
                signal_line = macd_line.ewm(span=9, min_periods=1).mean()
                histogram = macd_line - signal_line
                
                if len(histogram) >= 2:
                    current_hist = safe_float(histogram.iloc[-1])
                    prev_hist = safe_float(histogram.iloc[-2])
                    
                    if current_hist > prev_hist and current_hist > 0:
                        technical_analysis['macd_signal'] = '金叉向上'
                    elif current_hist < prev_hist and current_hist < 0:
                        technical_analysis['macd_signal'] = '死叉向下'
                    else:
                        technical_analysis['macd_signal'] = '横盘整理'
                else:
                    technical_analysis['macd_signal'] = '数据不足'
                
            except Exception as e:
                technical_analysis['macd_signal'] = '计算失败'
            
            # 布林带
            try:
                bb_window = min(20, len(price_data))
                bb_middle = price_data['close'].rolling(window=bb_window, min_periods=1).mean()
                bb_std = price_data['close'].rolling(window=bb_window, min_periods=1).std()
                bb_upper = bb_middle + 2 * bb_std
                bb_lower = bb_middle - 2 * bb_std
                
                latest_close = safe_float(price_data['close'].iloc[-1])
                bb_upper_val = safe_float(bb_upper.iloc[-1])
                bb_lower_val = safe_float(bb_lower.iloc[-1])
                
                if bb_upper_val != bb_lower_val and bb_upper_val > bb_lower_val:
                    bb_position = (latest_close - bb_lower_val) / (bb_upper_val - bb_lower_val)
                    technical_analysis['bb_position'] = safe_float(bb_position, 0.5)
                else:
                    technical_analysis['bb_position'] = 0.5
                
            except Exception as e:
                technical_analysis['bb_position'] = 0.5
            
            # 成交量分析
            try:
                volume_window = min(20, len(price_data))
                avg_volume = price_data['volume'].rolling(window=volume_window, min_periods=1).mean().iloc[-1]
                recent_volume = safe_float(price_data['volume'].iloc[-1])
                
                if 'change_pct' in price_data.columns:
                    price_change = safe_float(price_data['change_pct'].iloc[-1])
                elif len(price_data) >= 2:
                    current_price = safe_float(price_data['close'].iloc[-1])
                    prev_price = safe_float(price_data['close'].iloc[-2])
                    if prev_price > 0:
                        price_change = ((current_price - prev_price) / prev_price) * 100
                    else:
                        price_change = 0
                else:
                    price_change = 0
                
                avg_volume = safe_float(avg_volume, recent_volume)
                if recent_volume > avg_volume * 1.2:
                    technical_analysis['volume_status'] = '放量上涨' if price_change > 0 else '放量下跌'
                elif recent_volume < avg_volume * 0.8:
                    technical_analysis['volume_status'] = '缩量回调' if price_change < 0 else '缩量整理'
                else:
                    technical_analysis['volume_status'] = '量能平稳'
                
            except Exception as e:
                technical_analysis['volume_status'] = '数据不足'
            
            return technical_analysis
            
        except Exception as e:
            self.logger.error(f"技术指标计算失败: {str(e)}")
            return self._get_default_technical_analysis()

    def _get_default_technical_analysis(self):
        """获取默认技术分析结果"""
        return {
            'ma_trend': '数据不足',
            'rsi': 50.0,
            'macd_signal': '数据不足',
            'bb_position': 0.5,
            'volume_status': '数据不足'
        }

    def calculate_technical_score(self, technical_analysis):
        """计算技术分析得分"""
        try:
            score = 50
            
            ma_trend = technical_analysis.get('ma_trend', '数据不足')
            if ma_trend == '多头排列':
                score += 20
            elif ma_trend == '空头排列':
                score -= 20
            
            rsi = technical_analysis.get('rsi', 50)
            if 30 <= rsi <= 70:
                score += 10
            elif rsi < 30:
                score += 5
            elif rsi > 70:
                score -= 5
            
            macd_signal = technical_analysis.get('macd_signal', '横盘整理')
            if macd_signal == '金叉向上':
                score += 15
            elif macd_signal == '死叉向下':
                score -= 15
            
            bb_position = technical_analysis.get('bb_position', 0.5)
            if 0.2 <= bb_position <= 0.8:
                score += 5
            elif bb_position < 0.2:
                score += 10
            elif bb_position > 0.8:
                score -= 5
            
            volume_status = technical_analysis.get('volume_status', '数据不足')
            if '放量上涨' in volume_status:
                score += 10
            elif '放量下跌' in volume_status:
                score -= 10
            
            score = max(0, min(100, score))
            return score
            
        except Exception as e:
            self.logger.error(f"技术分析评分失败: {str(e)}")
            return 50

    def calculate_fundamental_score(self, fundamental_data):
        """计算基本面得分"""
        try:
            score = 50
            
            # 财务指标评分
            financial_indicators = fundamental_data.get('financial_indicators', {})
            if len(financial_indicators) >= 15:  # 有足够的财务指标
                score += 20
                
                # 盈利能力评分
                roe = financial_indicators.get('净资产收益率', 0)
                if roe > 15:
                    score += 10
                elif roe > 10:
                    score += 5
                elif roe < 5:
                    score -= 5
                
                # 偿债能力评分
                debt_ratio = financial_indicators.get('资产负债率', 50)
                if debt_ratio < 30:
                    score += 5
                elif debt_ratio > 70:
                    score -= 10
                
                # 成长性评分
                revenue_growth = financial_indicators.get('营收同比增长率', 0)
                if revenue_growth > 20:
                    score += 10
                elif revenue_growth > 10:
                    score += 5
                elif revenue_growth < -10:
                    score -= 10
            
            # 估值评分
            valuation = fundamental_data.get('valuation', {})
            if valuation:
                score += 10
            
            # 业绩预告评分
            performance_forecast = fundamental_data.get('performance_forecast', [])
            if performance_forecast:
                score += 10
            
            score = max(0, min(100, score))
            return score
            
        except Exception as e:
            self.logger.error(f"基本面评分失败: {str(e)}")
            return 50

    def calculate_sentiment_score(self, sentiment_analysis):
        """计算情绪分析得分"""
        try:
            overall_sentiment = sentiment_analysis.get('overall_sentiment', 0.0)
            confidence_score = sentiment_analysis.get('confidence_score', 0.0)
            total_analyzed = sentiment_analysis.get('total_analyzed', 0)
            
            # 基础得分：将情绪得分从[-1,1]映射到[0,100]
            base_score = (overall_sentiment + 1) * 50
            
            # 置信度调整
            confidence_adjustment = confidence_score * 10
            
            # 新闻数量调整
            news_adjustment = min(total_analyzed / 100, 1.0) * 10
            
            final_score = base_score + confidence_adjustment + news_adjustment
            final_score = max(0, min(100, final_score))
            
            return final_score
            
        except Exception as e:
            self.logger.error(f"情绪得分计算失败: {e}")
            return 50

    def calculate_comprehensive_score(self, scores):
        """计算综合得分"""
        try:
            technical_score = scores.get('technical', 50)
            fundamental_score = scores.get('fundamental', 50)
            sentiment_score = scores.get('sentiment', 50)
            
            comprehensive_score = (
                technical_score * self.analysis_weights['technical'] +
                fundamental_score * self.analysis_weights['fundamental'] +
                sentiment_score * self.analysis_weights['sentiment']
            )
            
            comprehensive_score = max(0, min(100, comprehensive_score))
            return comprehensive_score
            
        except Exception as e:
            self.logger.error(f"计算综合得分失败: {e}")
            return 50

    def get_stock_name(self, stock_code):
        """获取股票名称"""
        try:
            stock_meta = self._normalize_stock_code(stock_code)
            market = stock_meta['market']
            symbol = stock_meta['ak_symbol']

            if market != 'cn_a':
                return stock_meta['display_code']
            
            try:
                stock_info = self._call_akshare_api(
                    'stock_individual_info_em',
                    retries=1,
                    retry_delay=0.3,
                    log_failure=False,
                    symbol=symbol
                )
                if stock_info is not None and not stock_info.empty:
                    info_dict = dict(zip(stock_info['item'], stock_info['value']))
                    stock_name = info_dict.get('股票简称', stock_meta['display_code'])
                    if stock_name and stock_name != stock_meta['display_code']:
                        return stock_name
            except Exception as e:
                self.logger.warning(f"获取股票名称失败: {e}")
            
            return stock_meta['display_code']
            
        except Exception as e:
            self.logger.warning(f"获取股票名称时出错: {e}")
            return self._normalize_stock_code(stock_code)['display_code']

    def get_price_info(self, price_data):
        """从价格数据中提取关键信息 - 修复版本"""
        try:
            if price_data.empty or 'close' not in price_data.columns:
                self.logger.warning("价格数据为空或缺少收盘价列")
                return {
                    'current_price': 0.0,
                    'price_change': 0.0,
                    'volume_ratio': 1.0,
                    'volatility': 0.0
                }
            
            # 获取最新数据
            latest = price_data.iloc[-1]
            
            # 确保使用收盘价作为当前价格
            current_price = float(latest['close'])
            self.logger.info(f"✓ 当前价格(收盘价): {current_price}")
            
            # 如果收盘价异常，尝试使用其他价格
            if pd.isna(current_price) or current_price <= 0:
                if 'open' in price_data.columns and not pd.isna(latest['open']) and latest['open'] > 0:
                    current_price = float(latest['open'])
                    self.logger.warning(f"⚠️ 收盘价异常，使用开盘价: {current_price}")
                elif 'high' in price_data.columns and not pd.isna(latest['high']) and latest['high'] > 0:
                    current_price = float(latest['high'])
                    self.logger.warning(f"⚠️ 收盘价异常，使用最高价: {current_price}")
                else:
                    self.logger.error(f"❌ 所有价格数据都异常")
                    return {
                        'current_price': 0.0,
                        'price_change': 0.0,
                        'volume_ratio': 1.0,
                        'volatility': 0.0
                    }
            
            # 安全的数值处理函数
            def safe_float(value, default=0.0):
                try:
                    if pd.isna(value):
                        return default
                    num_value = float(value)
                    if math.isnan(num_value) or math.isinf(num_value):
                        return default
                    return num_value
                except (ValueError, TypeError):
                    return default
            
            # 计算价格变化
            price_change = 0.0
            try:
                if 'change_pct' in price_data.columns and not pd.isna(latest['change_pct']):
                    price_change = safe_float(latest['change_pct'])
                    self.logger.info(f"✓ 使用现成的涨跌幅: {price_change}%")
                elif len(price_data) > 1:
                    prev = price_data.iloc[-2]
                    prev_price = safe_float(prev['close'])
                    if prev_price > 0:
                        price_change = safe_float(((current_price - prev_price) / prev_price * 100))
                        self.logger.info(f"✓ 计算涨跌幅: {price_change}%")
            except Exception as e:
                self.logger.warning(f"计算价格变化失败: {e}")
                price_change = 0.0
            
            # 计算成交量比率
            volume_ratio = 1.0
            try:
                if 'volume' in price_data.columns:
                    volume_data = price_data['volume'].dropna()
                    if len(volume_data) >= 20:
                        recent_volume = volume_data.iloc[-1]
                        avg_volume = volume_data.tail(20).mean()
                        if avg_volume > 0:
                            volume_ratio = safe_float(recent_volume / avg_volume, 1.0)
                    elif len(volume_data) >= 5:
                        recent_volume = volume_data.tail(5).mean()
                        avg_volume = volume_data.mean()
                        if avg_volume > 0:
                            volume_ratio = safe_float(recent_volume / avg_volume, 1.0)
            except Exception as e:
                self.logger.warning(f"计算成交量比率失败: {e}")
                volume_ratio = 1.0
            
            # 计算波动率
            volatility = 0.0
            try:
                close_prices = price_data['close'].dropna()
                if len(close_prices) >= 20:
                    returns = close_prices.pct_change().dropna()
                    if len(returns) >= 20:
                        volatility = safe_float(returns.tail(20).std() * 100)
            except Exception as e:
                self.logger.warning(f"计算波动率失败: {e}")
                volatility = 0.0
            
            result = {
                'current_price': safe_float(current_price),
                'price_change': safe_float(price_change),
                'volume_ratio': safe_float(volume_ratio, 1.0),
                'volatility': safe_float(volatility)
            }
            
            self.logger.info(f"✓ 价格信息提取完成: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"获取价格信息失败: {e}")
            return {
                'current_price': 0.0,
                'price_change': 0.0,
                'volume_ratio': 1.0,
                'volatility': 0.0
            }

    def _normalize_position_cost(self, position_cost):
        """标准化用户输入的持仓成本（元）"""
        if position_cost is None:
            return None
        text = str(position_cost).strip()
        if not text:
            return None
        text = text.replace(',', '')
        try:
            value = float(text)
            if value <= 0 or math.isnan(value) or math.isinf(value):
                return None
            return round(value, 4)
        except Exception:
            return None

    def _build_position_context(self, position_cost, current_price):
        """基于持仓成本和当前价格构建持仓上下文"""
        normalized_cost = self._normalize_position_cost(position_cost)
        if normalized_cost is None:
            return {
                'has_position_cost': False,
                'position_cost': None,
                'current_price': float(current_price or 0.0) if current_price is not None else 0.0,
                'pnl_amount': None,
                'pnl_pct': None,
                'position_state': '未提供成本'
            }

        try:
            current = float(current_price or 0.0)
            if math.isnan(current) or math.isinf(current):
                current = 0.0
        except Exception:
            current = 0.0

        pnl_amount = current - normalized_cost
        pnl_pct = (pnl_amount / normalized_cost * 100.0) if normalized_cost > 0 else 0.0

        if pnl_amount > 1e-8:
            state = '浮盈'
        elif pnl_amount < -1e-8:
            state = '浮亏'
        else:
            state = '保本'

        return {
            'has_position_cost': True,
            'position_cost': normalized_cost,
            'current_price': round(current, 4),
            'pnl_amount': round(pnl_amount, 4),
            'pnl_pct': round(pnl_pct, 4),
            'position_state': state
        }

    def generate_recommendation(self, scores, technical_analysis=None, sentiment_analysis=None, price_info=None):
        """根据得分与风险状态生成投资建议"""
        try:
            technical_analysis = technical_analysis or {}
            sentiment_analysis = sentiment_analysis or {}
            price_info = price_info or {}

            comprehensive_score = float(scores.get('comprehensive', 50))
            technical_score = float(scores.get('technical', 50))
            fundamental_score = float(scores.get('fundamental', 50))
            sentiment_score = float(scores.get('sentiment', 50))

            volatility = abs(float(price_info.get('volatility', 0.0) or 0.0))
            confidence = float(sentiment_analysis.get('confidence_score', 0.5) or 0.5)
            overall_sentiment = float(sentiment_analysis.get('overall_sentiment', 0.0) or 0.0)
            ma_trend = str(technical_analysis.get('ma_trend', ''))

            risk_penalty = 0
            if volatility >= 8:
                risk_penalty += 10
            elif volatility >= 5:
                risk_penalty += 6

            if confidence < 0.25:
                risk_penalty += 6
            elif confidence < 0.45:
                risk_penalty += 3

            if overall_sentiment < -0.3:
                risk_penalty += 6
            elif overall_sentiment < -0.1:
                risk_penalty += 3

            if ma_trend == '空头排列':
                risk_penalty += 4

            adjusted_score = max(0, min(100, comprehensive_score - risk_penalty))

            if adjusted_score >= 82 and technical_score >= 70 and fundamental_score >= 70:
                return "分批买入"
            if adjusted_score >= 70:
                return "偏多持有"
            if adjusted_score >= 55 and sentiment_score >= 50:
                return "轻仓试探"
            if adjusted_score >= 40:
                return "持有观望"
            if adjusted_score >= 28:
                return "减仓防守"
            return "回避为主"

        except Exception as e:
            self.logger.warning(f"生成投资建议失败: {e}")
            return "数据不足，建议谨慎"

    def generate_strategy_plan(self, scores, technical_analysis=None, sentiment_analysis=None, price_info=None):
        """生成结构化策略计划，便于前端和导出使用"""
        try:
            technical_analysis = technical_analysis or {}
            sentiment_analysis = sentiment_analysis or {}
            price_info = price_info or {}

            comprehensive = float(scores.get('comprehensive', 50) or 50)
            volatility = abs(float(price_info.get('volatility', 0.0) or 0.0))
            confidence = float(sentiment_analysis.get('confidence_score', 0.5) or 0.5)
            sentiment = float(sentiment_analysis.get('overall_sentiment', 0.0) or 0.0)

            if comprehensive >= 75 and volatility < 4 and sentiment >= 0:
                risk_level = "低"
                position = "60%-80%"
                entry_strategy = "分2-3批逐步建仓，回踩5日或10日均线附近优先"
            elif comprehensive >= 60 and volatility < 6:
                risk_level = "中"
                position = "35%-55%"
                entry_strategy = "先小仓位试探，技术信号确认后再加仓"
            elif comprehensive >= 45:
                risk_level = "中高"
                position = "15%-30%"
                entry_strategy = "仅观察或极轻仓，等待趋势明确"
            else:
                risk_level = "高"
                position = "0%-15%"
                entry_strategy = "以防守为主，不建议主动加仓"

            if confidence < 0.35:
                position = "0%-25%" if risk_level in ("中高", "高") else "20%-40%"

            stop_loss = "8%-10%" if volatility >= 6 else "5%-8%"
            take_profit = "15%-25%" if comprehensive >= 65 else "10%-18%"
            holding_period = "中线(1-3个月)" if comprehensive >= 60 else "短中结合(2-8周)"

            return {
                'risk_level': risk_level,
                'suggested_position': position,
                'entry_strategy': entry_strategy,
                'stop_loss_range': stop_loss,
                'take_profit_range': take_profit,
                'holding_period': holding_period,
                'confidence_score': round(confidence, 3),
                'sentiment_score': round(sentiment, 3),
                'volatility': round(volatility, 3)
            }
        except Exception as e:
            self.logger.warning(f"生成结构化策略失败: {e}")
            return {
                'risk_level': '未知',
                'suggested_position': '谨慎',
                'entry_strategy': '数据不足，建议等待更多确认信号',
                'stop_loss_range': '5%-8%',
                'take_profit_range': '10%-15%',
                'holding_period': '中短线',
                'confidence_score': 0.0,
                'sentiment_score': 0.0,
                'volatility': 0.0
            }

    def _build_enhanced_ai_analysis_prompt(
        self,
        stock_code,
        stock_name,
        scores,
        technical_analysis,
        fundamental_data,
        sentiment_analysis,
        price_info,
        position_context=None
    ):
        """构建增强版AI分析提示词，包含所有详细数据"""
        
        # 提取25项财务指标
        financial_indicators = fundamental_data.get('financial_indicators', {})
        financial_text = ""
        if financial_indicators:
            financial_text = "**25项核心财务指标：**\n"
            for i, (key, value) in enumerate(financial_indicators.items(), 1):
                if isinstance(value, (int, float)) and value != 0:
                    financial_text += f"{i}. {key}: {value}\n"
        
        # 新闻压缩信息（主模型输入）
        compressed_news_context = sentiment_analysis.get('compressed_news_context', {})
        if not isinstance(compressed_news_context, dict) or not compressed_news_context.get('summary_text'):
            compressed_news_context = self._build_compressed_news_context(sentiment_analysis)

        source_counts = compressed_news_context.get('source_counts', {})
        total_news_count = int(
            compressed_news_context.get('total_news_count', sentiment_analysis.get('total_analyzed', 0)) or 0
        )
        raw_news_len = int(compressed_news_context.get('raw_text_length', 0) or 0)
        compressed_news_len = int(compressed_news_context.get('compressed_text_length', 0) or 0)
        compression_ratio = float(compressed_news_context.get('compression_ratio', 1.0) or 1.0)
        reduced_percent = max(0.0, min(99.9, (1.0 - compression_ratio) * 100.0)) if raw_news_len > 0 else 0.0
        compressed_summary_text = compressed_news_context.get('summary_text', '暂无可用新闻摘要。')

        json_model_meta = ""
        if compressed_news_context.get('llm_json_mode_used'):
            json_model_meta = (
                f"\n- JSON新闻模型：{sentiment_analysis.get('json_model_provider', '')} / "
                f"{sentiment_analysis.get('json_model_name', '')}"
            )

        news_text = f"""
**新闻压缩输入（已喂给主分析模型）：**
- 总新闻数：{total_news_count}条
- 公司新闻：{source_counts.get('company_news', 0)}条
- 公司公告：{source_counts.get('announcements', 0)}条
- 研究报告：{source_counts.get('research_reports', 0)}条
- 行业新闻：{source_counts.get('industry_news', 0)}条
- 压缩前文本长度：{raw_news_len} 字符
- 压缩后文本长度：{compressed_news_len} 字符
- 预计压缩率：{reduced_percent:.1f}%{json_model_meta}

**压缩摘要正文：**
{compressed_summary_text}
"""

        position_context = position_context if isinstance(position_context, dict) else {}
        if position_context.get('has_position_cost'):
            position_text = f"""
**持仓信息（用户输入）：**
- 持仓成本：{position_context.get('position_cost', 0):.4f}元
- 当前价格：{position_context.get('current_price', 0):.4f}元
- 当前状态：{position_context.get('position_state', '未知')}
- 每股浮盈亏：{position_context.get('pnl_amount', 0):+.4f}元
- 持仓收益率：{position_context.get('pnl_pct', 0):+.2f}%
"""
        else:
            position_text = """
**持仓信息：**
- 用户未提供持仓成本，请按通用策略给出建议。
"""
        
        # 构建完整的提示词
        prompt = f"""请作为一位资深的股票分析师，基于以下详细数据对股票进行深度分析：

**股票基本信息：**
- 股票代码：{stock_code}
- 股票名称：{stock_name}
- 当前价格：{price_info.get('current_price', 0):.2f}元
- 涨跌幅：{price_info.get('price_change', 0):.2f}%
- 成交量比率：{price_info.get('volume_ratio', 1):.2f}
- 波动率：{price_info.get('volatility', 0):.2f}%

{position_text}

**技术分析详情：**
- 均线趋势：{technical_analysis.get('ma_trend', '未知')}
- RSI指标：{technical_analysis.get('rsi', 50):.1f}
- MACD信号：{technical_analysis.get('macd_signal', '未知')}
- 布林带位置：{technical_analysis.get('bb_position', 0.5):.2f}
- 成交量状态：{technical_analysis.get('volume_status', '未知')}

{financial_text}

**估值指标：**
{self._format_dict_data(fundamental_data.get('valuation', {}))}

**业绩预告：**
共{len(fundamental_data.get('performance_forecast', []))}条业绩预告
{self._format_list_data(fundamental_data.get('performance_forecast', [])[:3])}

**分红配股：**
共{len(fundamental_data.get('dividend_info', []))}条分红配股信息
{self._format_list_data(fundamental_data.get('dividend_info', [])[:3])}

{news_text}

**市场情绪分析：**
- 整体情绪得分：{sentiment_analysis.get('overall_sentiment', 0):.3f}
- 情绪趋势：{sentiment_analysis.get('sentiment_trend', '中性')}
- 置信度：{sentiment_analysis.get('confidence_score', 0):.2f}
- 各类新闻情绪：{sentiment_analysis.get('sentiment_by_type', {})}

**综合评分：**
- 技术面得分：{scores.get('technical', 50):.1f}/100
- 基本面得分：{scores.get('fundamental', 50):.1f}/100
- 情绪面得分：{scores.get('sentiment', 50):.1f}/100
- 综合得分：{scores.get('comprehensive', 50):.1f}/100

**分析要求：**

请基于以上详细数据，从以下维度进行深度分析：

1. **财务健康度深度解读**：
   - 基于25项财务指标，全面评估公司财务状况
   - 识别财务优势和风险点
   - 与行业平均水平对比分析
   - 预测未来财务发展趋势

2. **技术面精准分析**：
   - 结合多个技术指标，判断短中长期趋势
   - 识别关键支撑位和阻力位
   - 分析成交量与价格的配合关系
   - 评估当前位置的风险收益比

3. **市场情绪深度挖掘**：
   - 分析公司新闻、公告、研报的影响
   - 评估市场对公司的整体预期
   - 识别情绪拐点和催化剂
   - 判断情绪对股价的推动或拖累作用

4. **基本面价值判断**：
   - 评估公司内在价值和成长潜力
   - 分析行业地位和竞争优势
   - 评估业绩预告和分红政策
   - 判断当前估值的合理性

5. **综合投资策略**：
   - 给出明确的买卖建议和理由
   - 设定目标价位和止损点
   - 制定分批操作策略
   - 评估投资时间周期

6. **风险机会识别**：
   - 列出主要投资风险和应对措施
   - 识别潜在催化剂和成长机会
   - 分析宏观环境和政策影响
   - 提供动态调整建议

7. **持仓针对性建议（如有持仓成本）**：
   - 明确成本位附近的防守/止损策略
   - 给出分批减仓、加仓或做T的触发条件
   - 区分短线与中线两套执行路径

请用专业、客观的语言进行分析，确保逻辑清晰、数据支撑充分、结论明确可执行。"""

        return prompt

    def _format_dict_data(self, data_dict, max_items=5):
        """格式化字典数据"""
        if not data_dict:
            return "无数据"
        
        formatted = ""
        for i, (key, value) in enumerate(data_dict.items()):
            if i >= max_items:
                break
            formatted += f"- {key}: {value}\n"
        
        return formatted if formatted else "无有效数据"

    def _format_list_data(self, data_list, max_items=3):
        """格式化列表数据"""
        if not data_list:
            return "无数据"
        
        formatted = ""
        for i, item in enumerate(data_list):
            if i >= max_items:
                break
            if isinstance(item, dict):
                # 取字典的前几个键值对
                item_str = ", ".join([f"{k}: {v}" for k, v in list(item.items())[:3]])
                formatted += f"- {item_str}\n"
            else:
                formatted += f"- {item}\n"
        
        return formatted if formatted else "无有效数据"

    def generate_ai_analysis(self, analysis_data, enable_streaming=False, stream_callback=None):
        """生成AI增强分析 - 支持流式输出"""
        try:
            self.logger.info("🤖 开始AI深度分析...")
            
            stock_code = analysis_data.get('stock_code', '')
            stock_name = analysis_data.get('stock_name', stock_code)
            scores = analysis_data.get('scores', {})
            technical_analysis = analysis_data.get('technical_analysis', {})
            fundamental_data = analysis_data.get('fundamental_data', {})
            sentiment_analysis = analysis_data.get('sentiment_analysis', {})
            price_info = analysis_data.get('price_info', {})
            position_context = analysis_data.get('position_context', {})
            
            # 构建增强版AI分析提示词
            prompt = self._build_enhanced_ai_analysis_prompt(
                stock_code, stock_name, scores, technical_analysis, 
                fundamental_data, sentiment_analysis, price_info, position_context
            )
            
            # 调用AI API（支持流式）
            ai_response = self._call_ai_api(prompt, enable_streaming, stream_callback)
            
            if ai_response:
                self.logger.info("✅ AI深度分析完成")
                return ai_response
            else:
                self.logger.warning("⚠️ AI API不可用，使用高级分析模式")
                return self._advanced_rule_based_analysis(analysis_data)
                
        except Exception as e:
            self.logger.error(f"AI分析失败: {e}")
            return self._advanced_rule_based_analysis(analysis_data)

    def _call_ai_api(self, prompt, enable_streaming=False, stream_callback=None):
        """调用AI API - 支持流式输出"""
        try:
            model_preference = str(
                self.config.get('ai', {}).get('model_preference', 'openai')
            ).strip().lower()
            provider_alias = {
                'claude': 'anthropic',
                'silicon-flow': 'siliconflow'
            }
            model_preference = provider_alias.get(model_preference, model_preference)

            provider_callers = {
                'openai': self._call_openai_api,
                'siliconflow': self._call_siliconflow_api,
                'anthropic': self._call_claude_api,
                'zhipu': self._call_zhipu_api
            }

            ordered_providers = [model_preference, 'openai', 'siliconflow', 'anthropic', 'zhipu']
            seen = set()
            for provider in ordered_providers:
                if provider in seen:
                    continue
                seen.add(provider)

                caller = provider_callers.get(provider)
                if not caller or not self.api_keys.get(provider):
                    continue

                if provider != model_preference:
                    self.logger.info(f"尝试备用{provider} API...")

                result = caller(prompt, enable_streaming, stream_callback)
                if result:
                    return result

            return None
                
        except Exception as e:
            self.logger.error(f"AI API调用失败: {e}")
            return None

    def _extract_text_content(self, content):
        """兼容不同SDK响应结构，提取文本内容"""
        def _repair_text(text):
            """修复常见乱码（UTF-8被按Latin-1误解码）"""
            if not isinstance(text, str) or not text:
                return text

            # 仅在明显出现乱码特征时尝试修复，避免误伤正常文本
            mojibake_markers = ('Ã', 'Â', 'å', 'ä', 'è', 'ç', 'æ', 'ï¼', 'ã')
            marker_hits = sum(text.count(m) for m in mojibake_markers)
            has_cjk = bool(re.search(r'[\u4e00-\u9fff]', text))
            if marker_hits < 3 and has_cjk:
                return text

            try:
                repaired = text.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
                if repaired and (bool(re.search(r'[\u4e00-\u9fff]', repaired)) or repaired.count('?') < text.count('?')):
                    return repaired
            except Exception:
                pass

            return text

        if content is None:
            return ""

        if isinstance(content, str):
            return _repair_text(content)

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(_repair_text(item))
                    continue
                if isinstance(item, dict):
                    text = item.get('text')
                    if isinstance(text, str) and text:
                        text_parts.append(_repair_text(text))
                    elif isinstance(item.get('content'), str):
                        text_parts.append(_repair_text(item.get('content')))
            return "".join(text_parts)

        if isinstance(content, dict):
            if isinstance(content.get('text'), str):
                return _repair_text(content.get('text'))
            if isinstance(content.get('content'), str):
                return _repair_text(content.get('content'))

        return _repair_text(str(content))

    def _extract_stream_delta_text(self, delta):
        """从流式delta中提取增量文本"""
        if delta is None:
            return ""

        if isinstance(delta, dict):
            content = delta.get('content')
            return self._extract_text_content(content)

        if hasattr(delta, 'content'):
            return self._extract_text_content(getattr(delta, 'content'))

        return self._extract_text_content(delta)

    def _call_openai_compatible_api(
        self,
        provider,
        prompt,
        enable_streaming=False,
        stream_callback=None,
        system_prompt=None,
        model_override=None,
        max_tokens_override=None,
        temperature_override=None,
        require_json=False
    ):
        """调用OpenAI兼容接口（OpenAI/SiliconFlow）"""
        try:
            api_key = self.api_keys.get(provider)
            if not api_key:
                return None

            ai_config = self.config.get('ai', {})
            api_base_urls = ai_config.get('api_base_urls', {})
            default_base = {
                'openai': 'https://api.openai.com/v1',
                'siliconflow': 'https://api.siliconflow.cn/v1'
            }
            api_base = str(api_base_urls.get(provider) or default_base.get(provider, '')).strip()
            if not api_base:
                self.logger.error(f"{provider} API Base 未配置")
                return None

            model = str(model_override or self._get_provider_model(provider)).strip()
            max_tokens = int(max_tokens_override or ai_config.get('max_tokens', 6000))
            temperature = float(
                ai_config.get('temperature', 0.7)
                if temperature_override is None
                else temperature_override
            )

            final_system_prompt = system_prompt or "你是一位资深的股票分析师，请提供专业、客观、有深度的股票分析。"
            messages = [
                {"role": "system", "content": final_system_prompt},
                {"role": "user", "content": prompt}
            ]

            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            if require_json:
                payload["response_format"] = {"type": "json_object"}

            url = f"{api_base.rstrip('/')}/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            self.logger.info(f"正在调用{provider}兼容接口模型 {model} ...")

            def _is_retryable_http_error(exc):
                try:
                    status_code = exc.response.status_code if exc.response is not None else None
                    return status_code is not None and status_code >= 500
                except Exception:
                    return False

            if enable_streaming and stream_callback:
                payload["stream"] = True
                for attempt in range(2):
                    try:
                        with requests.post(
                            url,
                            headers=headers,
                            json=payload,
                            timeout=(20, 300),
                            stream=True
                        ) as response:
                            response.raise_for_status()

                            full_response = ""
                            for raw_line in response.iter_lines(decode_unicode=False):
                                if not raw_line:
                                    continue
                                if isinstance(raw_line, (bytes, bytearray)):
                                    line = raw_line.decode('utf-8', errors='replace').strip()
                                else:
                                    line = str(raw_line).strip()
                                if not line.startswith("data:"):
                                    continue
                                data = line[5:].strip()
                                if data == "[DONE]":
                                    break

                                try:
                                    chunk = json.loads(data)
                                    choices = chunk.get('choices', [])
                                    if not choices:
                                        continue
                                    delta = choices[0].get('delta', {})
                                    content = self._extract_stream_delta_text(delta)
                                    if content:
                                        full_response += content
                                        stream_callback(content)
                                except Exception:
                                    continue

                            return full_response
                    except requests.HTTPError as http_error:
                        if attempt < 1 and _is_retryable_http_error(http_error):
                            time.sleep(1.0)
                            continue
                        raise

            for attempt in range(2):
                try:
                    response = requests.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=(20, 240)
                    )
                    response.raise_for_status()
                    try:
                        response_data = json.loads(response.content.decode('utf-8', errors='replace'))
                    except Exception:
                        response_data = response.json()
                    choices = response_data.get('choices', [])
                    if not choices:
                        return None

                    message = choices[0].get('message', {})
                    return self._extract_text_content(message.get('content'))
                except requests.HTTPError as http_error:
                    if attempt < 1 and _is_retryable_http_error(http_error):
                        time.sleep(1.0)
                        continue
                    raise

        except Exception as e:
            self.logger.error(f"{provider}兼容API调用失败: {e}")
            return None

    def _call_openai_api(self, prompt, enable_streaming=False, stream_callback=None):
        """调用OpenAI API - 支持流式输出"""
        return self._call_openai_compatible_api(
            provider='openai',
            prompt=prompt,
            enable_streaming=enable_streaming,
            stream_callback=stream_callback
        )

    def _call_siliconflow_api(self, prompt, enable_streaming=False, stream_callback=None):
        """调用硅基流动API - 支持流式输出和JSON模式"""
        return self._call_openai_compatible_api(
            provider='siliconflow',
            prompt=prompt,
            enable_streaming=enable_streaming,
            stream_callback=stream_callback
        )

    def _call_claude_api(self, prompt, enable_streaming=False, stream_callback=None):
        """调用Claude API - 支持流式输出"""
        try:
            import anthropic
            
            api_key = self.api_keys.get('anthropic')
            if not api_key:
                return None
            
            client = anthropic.Anthropic(api_key=api_key)
            
            model = self.config.get('ai', {}).get('models', {}).get('anthropic', 'claude-3-haiku-20240307')
            max_tokens = self.config.get('ai', {}).get('max_tokens', 6000)
            
            self.logger.info(f"正在调用Claude {model} 进行深度分析...")
            
            if enable_streaming and stream_callback:
                # 流式调用
                with client.messages.stream(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                ) as stream:
                    full_response = ""
                    for text in stream.text_stream:
                        full_response += text
                        # 发送流式内容
                        if stream_callback:
                            stream_callback(text)
                
                return full_response
            else:
                # 非流式调用
                response = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                
                return response.content[0].text
            
        except Exception as e:
            self.logger.error(f"Claude API调用失败: {e}")
            return None

    def _call_zhipu_api(self, prompt, enable_streaming=False, stream_callback=None):
        """调用智谱AI API - 支持流式输出"""
        try:
            api_key = self.api_keys.get('zhipu')
            if not api_key:
                return None
            
            model = self.config.get('ai', {}).get('models', {}).get('zhipu', 'chatglm_turbo')
            max_tokens = self.config.get('ai', {}).get('max_tokens', 6000)
            temperature = self.config.get('ai', {}).get('temperature', 0.7)
            
            self.logger.info(f"正在调用智谱AI {model} 进行深度分析...")
            
            try:
                # 尝试新版本zhipuai库
                import zhipuai
                zhipuai.api_key = api_key
                
                # 尝试新的调用方式
                if hasattr(zhipuai, 'ZhipuAI'):
                    client = zhipuai.ZhipuAI(api_key=api_key)
                    
                    if enable_streaming and stream_callback:
                        # 流式调用
                        response = client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "user", "content": prompt}
                            ],
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stream=True
                        )
                        
                        full_response = ""
                        for chunk in response:
                            if chunk.choices[0].delta.content:
                                content = chunk.choices[0].delta.content
                                full_response += content
                                # 发送流式内容
                                if stream_callback:
                                    stream_callback(content)
                        
                        return full_response
                    else:
                        # 非流式调用
                        response = client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "user", "content": prompt}
                            ],
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                        return response.choices[0].message.content
                
                # 使用旧版本调用方式
                else:
                    # 注意：旧版本可能不支持流式
                    response = zhipuai.model_api.invoke(
                        model=model,
                        prompt=[
                            {"role": "user", "content": prompt}
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    # 处理不同的响应格式
                    if isinstance(response, dict):
                        if 'data' in response and 'choices' in response['data']:
                            return response['data']['choices'][0]['content']
                        elif 'choices' in response:
                            return response['choices'][0]['content']
                        elif 'data' in response:
                            return response['data']
                    
                    return str(response)
                    
            except ImportError:
                self.logger.error("智谱AI库未安装")
                return None
            except Exception as api_error:
                self.logger.error(f"智谱AI API调用错误: {api_error}")
                return None
            
        except Exception as e:
            self.logger.error(f"智谱AI API调用失败: {e}")
            return None

    def _advanced_rule_based_analysis(self, analysis_data):
        """高级规则分析（AI备用方案）"""
        try:
            self.logger.info("🧠 使用高级规则引擎进行分析...")
            
            stock_code = analysis_data.get('stock_code', '')
            stock_name = analysis_data.get('stock_name', stock_code)
            scores = analysis_data.get('scores', {})
            technical_analysis = analysis_data.get('technical_analysis', {})
            fundamental_data = analysis_data.get('fundamental_data', {})
            sentiment_analysis = analysis_data.get('sentiment_analysis', {})
            price_info = analysis_data.get('price_info', {})
            
            analysis_sections = []
            
            # 1. 综合评估
            comprehensive_score = scores.get('comprehensive', 50)
            analysis_sections.append(f"""## 📊 综合评估

基于技术面、基本面和市场情绪的综合分析，{stock_name}({stock_code})的综合得分为{comprehensive_score:.1f}分。

- 技术面得分：{scores.get('technical', 50):.1f}/100
- 基本面得分：{scores.get('fundamental', 50):.1f}/100  
- 情绪面得分：{scores.get('sentiment', 50):.1f}/100""")
            
            # 2. 财务分析
            financial_indicators = fundamental_data.get('financial_indicators', {})
            if financial_indicators:
                key_metrics = []
                for key, value in list(financial_indicators.items())[:10]:
                    if isinstance(value, (int, float)) and value != 0:
                        key_metrics.append(f"- {key}: {value}")
                
                financial_text = f"""## 💰 财务健康度分析

获取到{len(financial_indicators)}项财务指标，主要指标如下：

{chr(10).join(key_metrics[:8])}

财务健康度评估：{'优秀' if scores.get('fundamental', 50) >= 70 else '良好' if scores.get('fundamental', 50) >= 50 else '需关注'}"""
                analysis_sections.append(financial_text)
            
            # 3. 技术面分析
            tech_analysis = f"""## 📈 技术面分析

当前技术指标显示：
- 均线趋势：{technical_analysis.get('ma_trend', '未知')}
- RSI指标：{technical_analysis.get('rsi', 50):.1f}
- MACD信号：{technical_analysis.get('macd_signal', '未知')}
- 成交量状态：{technical_analysis.get('volume_status', '未知')}

技术面评估：{'强势' if scores.get('technical', 50) >= 70 else '中性' if scores.get('technical', 50) >= 50 else '偏弱'}"""
            analysis_sections.append(tech_analysis)
            
            # 4. 市场情绪
            sentiment_desc = f"""## 📰 市场情绪分析

基于{sentiment_analysis.get('total_analyzed', 0)}条新闻的分析：
- 整体情绪：{sentiment_analysis.get('sentiment_trend', '中性')}
- 情绪得分：{sentiment_analysis.get('overall_sentiment', 0):.3f}
- 置信度：{sentiment_analysis.get('confidence_score', 0):.2%}

新闻分布：
- 公司新闻：{len(sentiment_analysis.get('company_news', []))}条
- 公司公告：{len(sentiment_analysis.get('announcements', []))}条  
- 研究报告：{len(sentiment_analysis.get('research_reports', []))}条"""
            analysis_sections.append(sentiment_desc)

            if isinstance(position_context, dict) and position_context.get('has_position_cost'):
                position_desc = f"""## 🧾 持仓成本视角

- 持仓成本：{position_context.get('position_cost', 0):.4f} 元
- 当前价格：{position_context.get('current_price', 0):.4f} 元
- 当前状态：{position_context.get('position_state', '未知')}
- 每股浮盈亏：{position_context.get('pnl_amount', 0):+.4f} 元
- 持仓收益率：{position_context.get('pnl_pct', 0):+.2f}%"""
                analysis_sections.append(position_desc)
            
            # 5. 投资建议
            recommendation = self.generate_recommendation(
                scores,
                technical_analysis=technical_analysis,
                sentiment_analysis=sentiment_analysis,
                price_info=price_info
            )
            strategy_plan = self.generate_strategy_plan(
                scores,
                technical_analysis=technical_analysis,
                sentiment_analysis=sentiment_analysis,
                price_info=price_info
            )
            strategy = f"""## 🎯 投资策略建议

**投资建议：{recommendation}**

根据综合分析，建议如下：

{'**积极配置**：各项指标表现优异，可适当加大仓位。' if comprehensive_score >= 80 else 
 '**谨慎买入**：整体表现良好，但需要关注风险点。' if comprehensive_score >= 60 else
'**观望为主**：当前风险收益比一般，建议等待更好时机。' if comprehensive_score >= 40 else
'**规避风险**：多项指标显示风险较大，建议减仓或观望。'}

操作建议：
- 建议仓位：{strategy_plan.get('suggested_position', '谨慎')}
- 买入策略：{strategy_plan.get('entry_strategy', '等待确认')}
- 止损区间：{strategy_plan.get('stop_loss_range', '5%-8%')}
- 止盈区间：{strategy_plan.get('take_profit_range', '10%-15%')}
- 持有周期：{strategy_plan.get('holding_period', '中短线')}
- 风险等级：{strategy_plan.get('risk_level', '中')}"""
            analysis_sections.append(strategy)
            
            return "\n\n".join(analysis_sections)
            
        except Exception as e:
            self.logger.error(f"高级规则分析失败: {e}")
            return "分析系统暂时不可用，请稍后重试。"

    def set_streaming_config(self, enabled=True, show_thinking=True):
        """设置流式推理配置"""
        self.streaming_config.update({
            'enabled': enabled,
            'show_thinking': show_thinking
        })

    def analyze_stock(self, stock_code, enable_streaming=None, stream_callback=None, position_cost=None):
        """分析股票的主方法（修正版，支持AI流式输出）"""
        if enable_streaming is None:
            enable_streaming = self.streaming_config.get('enabled', False)
        
        try:
            stock_meta = self._normalize_stock_code(stock_code)
            normalized_stock_code = stock_meta['display_code']
            self.logger.info(f"开始增强版股票分析: {normalized_stock_code} ({stock_meta['market_label']})")
            
            # 获取股票名称
            stock_name = self.get_stock_name(stock_code)
            
            # 1. 获取价格数据和技术分析
            self.logger.info("正在进行技术分析...")
            price_data = self.get_stock_data(stock_code)
            if price_data.empty:
                raise ValueError(f"无法获取股票 {normalized_stock_code} 的价格数据")
            
            price_info = self.get_price_info(price_data)
            position_context = self._build_position_context(
                position_cost=position_cost,
                current_price=price_info.get('current_price', 0.0)
            )
            technical_analysis = self.calculate_technical_indicators(price_data)
            technical_score = self.calculate_technical_score(technical_analysis)
            
            # 2. 获取25项财务指标和综合基本面分析
            self.logger.info("正在进行25项财务指标分析...")
            fundamental_data = self.get_comprehensive_fundamental_data(stock_code)
            fundamental_score = self.calculate_fundamental_score(fundamental_data)
            
            # 3. 获取综合新闻数据和高级情绪分析
            self.logger.info("正在进行综合新闻和情绪分析...")
            comprehensive_news_data = self.get_comprehensive_news_data(stock_code, days=30)
            sentiment_analysis = self.calculate_advanced_sentiment_analysis(comprehensive_news_data)
            sentiment_score = self.calculate_sentiment_score(sentiment_analysis)
            
            # 合并新闻数据到情绪分析结果中，方便AI分析使用
            sentiment_analysis.update(comprehensive_news_data)
            sentiment_analysis['compressed_news_context'] = self._build_compressed_news_context(sentiment_analysis)
            compressed_meta = sentiment_analysis.get('compressed_news_context', {})
            self.logger.info(
                "✓ 新闻已压缩用于主模型: 原始%s字符 -> 压缩%s字符",
                compressed_meta.get('raw_text_length', 0),
                compressed_meta.get('compressed_text_length', 0)
            )
            
            # 4. 计算综合得分
            scores = {
                'technical': technical_score,
                'fundamental': fundamental_score,
                'sentiment': sentiment_score,
                'comprehensive': self.calculate_comprehensive_score({
                    'technical': technical_score,
                    'fundamental': fundamental_score,
                    'sentiment': sentiment_score
                })
            }
            
            # 5. 生成投资建议
            recommendation = self.generate_recommendation(
                scores,
                technical_analysis=technical_analysis,
                sentiment_analysis=sentiment_analysis,
                price_info=price_info
            )
            strategy_plan = self.generate_strategy_plan(
                scores,
                technical_analysis=technical_analysis,
                sentiment_analysis=sentiment_analysis,
                price_info=price_info
            )
            
            # 6. AI增强分析（包含所有详细数据，支持流式输出）
            ai_analysis = self.generate_ai_analysis({
                'stock_code': normalized_stock_code,
                'stock_name': stock_name,
                'price_info': price_info,
                'position_context': position_context,
                'technical_analysis': technical_analysis,
                'fundamental_data': fundamental_data,
                'sentiment_analysis': sentiment_analysis,
                'scores': scores
            }, enable_streaming, stream_callback)
            
            # 7. 生成最终报告
            report = {
                'stock_code': normalized_stock_code,
                'input_stock_code': stock_code,
                'stock_name': stock_name,
                'market': stock_meta['market_label'],
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'price_info': price_info,
                'position_context': position_context,
                'technical_analysis': technical_analysis,
                'fundamental_data': fundamental_data,
                'comprehensive_news_data': comprehensive_news_data,
                'sentiment_analysis': sentiment_analysis,
                'scores': scores,
                'analysis_weights': self.analysis_weights,
                'recommendation': recommendation,
                'strategy_plan': strategy_plan,
                'ai_analysis': ai_analysis,
                'data_quality': {
                    'financial_indicators_count': len(fundamental_data.get('financial_indicators', {})),
                    'total_news_count': sentiment_analysis.get('total_analyzed', 0),
                    'analysis_completeness': '完整' if len(fundamental_data.get('financial_indicators', {})) >= 15 else '部分'
                }
            }
            
            self.logger.info(f"✓ 增强版股票分析完成: {normalized_stock_code}")
            self.logger.info(f"  - 财务指标: {len(fundamental_data.get('financial_indicators', {}))} 项")
            self.logger.info(f"  - 新闻数据: {sentiment_analysis.get('total_analyzed', 0)} 条")
            self.logger.info(f"  - 综合得分: {scores['comprehensive']:.1f}")
            
            return report
            
        except Exception as e:
            self.logger.error(f"增强版股票分析失败 {stock_code}: {str(e)}")
            raise

    def analyze_stock_with_streaming(self, stock_code, streamer, position_cost=None):
        """带流式回调的股票分析方法"""
        def stream_callback(content):
            """AI流式内容回调"""
            if streamer:
                streamer.send_ai_stream(content)
        
        return self.analyze_stock(
            stock_code=stock_code,
            enable_streaming=True,
            stream_callback=stream_callback,
            position_cost=position_cost
        )

    # 兼容旧版本的方法名
    def get_fundamental_data(self, stock_code):
        """兼容方法：获取基本面数据"""
        return self.get_comprehensive_fundamental_data(stock_code)
    
    def get_news_data(self, stock_code, days=30):
        """兼容方法：获取新闻数据"""
        return self.get_comprehensive_news_data(stock_code, days)
    
    def calculate_news_sentiment(self, news_data):
        """兼容方法：计算新闻情绪"""
        return self.calculate_advanced_sentiment_analysis(news_data)
    
    def get_sentiment_analysis(self, stock_code):
        """兼容方法：获取情绪分析"""
        news_data = self.get_comprehensive_news_data(stock_code)
        return self.calculate_advanced_sentiment_analysis(news_data)


def main():
    """主函数"""
    analyzer = WebStockAnalyzer()
    
    # 测试分析
    test_stocks = ['000001', '600036', '300019', '000525']
    
    for stock_code in test_stocks:
        try:
            print(f"\n=== 开始增强版分析 {stock_code} (支持AI流式输出) ===")
            
            # 定义流式回调函数
            def print_stream(content):
                print(content, end='', flush=True)
            
            report = analyzer.analyze_stock(stock_code, enable_streaming=True, stream_callback=print_stream)
            
            print(f"\n股票代码: {report['stock_code']}")
            print(f"股票名称: {report['stock_name']}")
            print(f"当前价格: {report['price_info']['current_price']:.2f}元")
            print(f"涨跌幅: {report['price_info']['price_change']:.2f}%")
            print(f"财务指标数量: {report['data_quality']['financial_indicators_count']}")
            print(f"新闻数据量: {report['data_quality']['total_news_count']}")
            print(f"综合得分: {report['scores']['comprehensive']:.1f}")
            print(f"投资建议: {report['recommendation']}")
            print("=" * 60)
            
        except Exception as e:
            print(f"分析 {stock_code} 失败: {e}")


if __name__ == "__main__":
    main()
