import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dashscope import Generation
import os
from dotenv import load_dotenv

# 加载通义千问密钥（仅AI分析功能使用，无密钥不影响其他功能）
load_dotenv()
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# 页面基础配置
st.set_page_config(page_title="豆瓣电影热榜分析系统", layout="wide")

# 会话状态初始化
if "movie_df" not in st.session_state:
    st.session_state.movie_df = None
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False

# 启动时自动加载同目录下的Excel文件
try:
    df = pd.read_excel('豆瓣电影热榜数据.xlsx')
    st.session_state.movie_df = df
    st.session_state.data_loaded = True
except Exception as e:
    st.session_state.data_loaded = False
    st.session_state.load_error = str(e)

# 侧边栏布局
with st.sidebar:
    st.header("🎬 豆瓣电影热榜分析系统")
    st.divider()

    # 数据加载状态
    if st.session_state.data_loaded:
        st.success(f"数据状态: ✅ 已成功加载{len(st.session_state.movie_df)}条电影数据")
    else:
        st.error(f"数据状态: ❌ 数据加载失败")
        if "load_error" in st.session_state:
            st.error(f"错误信息: {st.session_state.load_error}")

    # 数据重置按钮
    if st.button("🔄 重新加载数据", use_container_width=True):
        try:
            df = pd.read_excel('豆瓣电影热榜数据.xlsx')
            st.session_state.movie_df = df
            st.session_state.data_loaded = True
            st.rerun()
        except Exception as e:
            st.error(f"重新加载失败: {str(e)}")

    st.divider()
    st.subheader("⚙️ 交互式筛选控制面板")
    df_temp = st.session_state.movie_df
    if df_temp is None or len(df_temp) == 0:
        st.info("暂无数据，筛选功能不可用")
        min_hot, max_hot = 0, 3500000
        min_rank, max_rank = 1, 2001
        year_list = ["全部"]
        type_list = ["全部"]
        min_score, max_score = 0, 10
    else:
        min_hot = int(df_temp["热度值"].min())
        max_hot = int(df_temp["热度值"].max())
        min_rank = int(df_temp["当前排名"].min())
        max_rank = int(df_temp["当前排名"].max())
        min_score = float(df_temp["评分"].min())
        max_score = float(df_temp["评分"].max())
        year_unique = sorted(df_temp["上映年份"].unique().tolist())
        type_unique = sorted(df_temp["影片分类"].unique().tolist())
        year_list = ["全部"] + year_unique
        type_list = ["全部"] + type_unique

    # 筛选控件
    hot_range = st.slider("热度区间筛选", min_hot, max_hot, (min_hot, max_hot))
    rank_range = st.slider("排名区间筛选", min_rank, max_rank, (min_rank, max_rank))
    score_range = st.slider("评分区间筛选", min_score, max_score, (min_score, max_score))
    sel_year = st.selectbox("筛选上映年份", year_list)
    sel_type = st.selectbox("筛选影片类型", type_list)

    st.divider()
    st.subheader("📋 功能导航菜单")
    menu_opt = st.radio("", ["数据概览", "可视化分析", "AI智能分析", "影片详情检索"])

# 数据筛选逻辑
def get_filtered_data():
    df = st.session_state.movie_df
    if df is None:
        return pd.DataFrame()
    f_df = df[
        (df["热度值"] >= hot_range[0]) & (df["热度值"] <= hot_range[1]) &
        (df["当前排名"] >= rank_range[0]) & (df["当前排名"] <= rank_range[1]) &
        (df["评分"] >= score_range[0]) & (df["评分"] <= score_range[1])
    ]
    if sel_year != "全部":
        f_df = f_df[f_df["上映年份"] == sel_year]
    if sel_type != "全部":
        f_df = f_df[f_df["影片分类"].str.contains(sel_type, na=False)]
    return f_df

filter_df = get_filtered_data()

# 页面功能模块
if menu_opt == "数据概览":
    st.header("📊 数据概览 | 豆瓣电影热榜大盘总览")
    if not st.session_state.data_loaded:
        st.warning("数据加载失败，请检查Excel文件是否正确上传")
    elif len(filter_df) == 0:
        st.warning("当前筛选条件无匹配数据，请修改侧边栏筛选条件")
    else:
        st.subheader("📌 大盘核心统计指标卡片")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        total_cnt = len(filter_df)
        total_hot = filter_df["热度值"].sum()
        avg_hot = round(filter_df["热度值"].mean(), 1)
        avg_score = round(filter_df["评分"].mean(), 2)
        top_name = filter_df.iloc[0]["影片名称"]
        top_hot_val = filter_df.iloc[0]["热度值"]

        with col1: st.metric("筛选后影片总数", total_cnt)
        with col2: st.metric("榜单总热度", f"{total_hot:,}")
        with col3: st.metric("平均热度值", f"{avg_hot:,}")
        with col4: st.metric("平均评分", avg_score)
        with col5: st.metric("热度榜首影片", top_name[:10]+"…")
        with col6: st.metric("榜首热度数值", f"{top_hot_val:,}")

        st.divider()
        st.subheader("📋 热榜明细表格（支持排序、滚动交互）")
        st.dataframe(filter_df, use_container_width=True, hide_index=True)

elif menu_opt == "可视化分析":
    st.header("📈 可视化分析 | 热度多维统计图")
    if not st.session_state.data_loaded:
        st.warning("数据加载失败，请检查Excel文件是否正确上传")
    elif len(filter_df) == 0:
        st.warning("当前筛选条件无匹配数据，请修改筛选条件")
    else:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "热度排行柱状图", "年份热度分布", "类型占比饼图",
            "评分-热度散点图", "年份数量分布"
        ])
        with tab1:
            fig_bar = px.bar(filter_df.head(20), x="影片名称", y="热度值", title="TOP20影片热度排行", text="热度值")
            fig_bar.update_layout(height=500, xaxis_tickangle=-45)
            st.plotly_chart(fig_bar, use_container_width=True)
        with tab2:
            year_group = filter_df.groupby("上映年份")["热度值"].sum().reset_index()
            fig_line = px.line(year_group, x="上映年份", y="热度值", title="各年份总热度趋势", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
        with tab3:
            # 拆分类型统计
            type_df = filter_df.assign(影片分类=filter_df["影片分类"].str.split("、")).explode("影片分类")
            type_group = type_df.groupby("影片分类")["热度值"].sum().reset_index()
            fig_pie = px.pie(type_group, names="影片分类", values="热度值", title="影片类型热度占比")
            st.plotly_chart(fig_pie, use_container_width=True)
        with tab4:
            fig_scatter = px.scatter(filter_df, x="评分", y="热度值", hover_data=["影片名称"], title="评分-热度相关性分布")
            st.plotly_chart(fig_scatter, use_container_width=True)
        with tab5:
            year_count = filter_df.groupby("上映年份")["影片名称"].count().reset_index()
            year_count.columns = ["上映年份", "影片数量"]
            fig_bar2 = px.bar(year_count, x="上映年份", y="影片数量", title="各年份影片数量分布")
            st.plotly_chart(fig_bar2, use_container_width=True)

elif menu_opt == "AI智能分析":
    st.header("🤖 AI智能分析 | 电影榜单深度解读（通义千问）")
    if not DASHSCOPE_API_KEY:
        st.error("通义千问密钥未配置，AI分析功能无法使用")
    elif not st.session_state.data_loaded:
        st.warning("数据加载失败，请检查Excel文件是否正确上传")
    elif len(filter_df) == 0:
        st.warning("暂无有效榜单数据，无法生成AI分析")
    else:
        user_prompt = st.text_area("输入你的分析提问（例如：分析热门电影趋势、推荐高分影片）",
                                   value="基于当前豆瓣电影热榜数据，做一份市场热度总结分析，包含热门类型、头部影片特点、行业趋势",
                                   height=120)

        # 优化后的AI生成逻辑：限制最多80条+超时+异常捕获，解决转圈卡顿
        if st.button("🚀 生成AI分析报告"):
            try:
                with st.spinner("AI思考生成中，请稍候..."):
                    # 最多只取前80行，大幅缩减输入文本，解决超长卡顿
                    send_df = filter_df.head(80)
                    df_text = send_df[["影片名称", "热度值", "评分", "上映年份", "影片分类", "制片国家/地区"]].to_string()

                    full_prompt = f"""以下是豆瓣电影热榜数据：
{df_text}
用户需求：{user_prompt}
要求分析条理清晰，分段易懂，适合课程作业展示总结。
"""
                    os.environ["DASHSCOPE_API_KEY"] = DASHSCOPE_API_KEY
                    rsp = Generation.call(
                        model="qwen-turbo",
                        prompt=full_prompt,
                        result_format="message",
                        timeout=25
                    )
                    if rsp.status_code == 200:
                        reply = rsp.output.choices[0].message.content
                        st.markdown("### ✅ AI分析结论")
                        st.write(reply)
                    else:
                        st.error(f"AI调用失败：{rsp.code} {rsp.message}")
            except Exception as e:
                st.error(f"生成超时或出错：{str(e)}，建议缩小筛选范围后重试")

elif menu_opt == "影片详情检索":
    st.header("🔍 影片详情检索 | 关键词模糊查询")
    if not st.session_state.data_loaded:
        st.warning("数据加载失败，请检查Excel文件是否正确上传")
    else:
        keyword = st.text_input("输入影片名称/导演/主演关键词搜索")
        if keyword:
            res_df = st.session_state.movie_df[
                st.session_state.movie_df["影片名称"].str.contains(keyword, case=False, na=False) |
                st.session_state.movie_df["导演"].str.contains(keyword, case=False, na=False) |
                st.session_state.movie_df["主演"].str.contains(keyword, case=False, na=False)
            ]
            if len(res_df) > 0:
                st.dataframe(res_df, use_container_width=True, hide_index=True)
            else:
                st.info("未查询到匹配影片")