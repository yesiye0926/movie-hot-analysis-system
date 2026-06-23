import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import plotly.express as px
import dashscope
from dashscope import Generation
import os
import requests
import numpy as np
from io import BytesIO

# 环境初始化
load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
api_token = os.getenv("MOVIE_API_KEY")

# 页面全局配置
st.set_page_config(
    page_title="夸克电影实时热榜交互分析系统",
    layout="wide",
    page_icon="🎬",
    initial_sidebar_state="expanded"
)

# 全局美化CSS（商务高分排版）
st.markdown("""
<style>
.main .block-container {padding: 1.5rem 2rem;}
h1 {font-size: 2.2rem; font-weight: 700; color:#1f2937; margin-bottom:1rem}
h2 {font-size:1.6rem; font-weight:600; margin-top:2rem; margin-bottom:1rem; border-left:5px solid #2563eb; padding-left:12px;}
h3 {font-size:1.3rem; font-weight:600; margin:1.2rem 0 0.8rem}
[data-testid="stMetric"] {
    background: linear-gradient(135deg,#f8fafc,#ffffff);
    padding:0.6rem 0.8rem;
    border-radius:10px;
    border-left:4px solid #2563eb;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
[data-testid="stMetricLabel"] p {font-size:0.9rem; color:#475569}
[data-testid="stMetricValue"] {font-size:1.5rem; font-weight:700; color:#0f172a}
div[data-testid="stSidebar"] {
    background:#f1f5f9;
    border-right:1px solid #e2e8f0;
}
.stTabs [data-baseweb="tab-list"] {gap:8px}
.stTabs [data-baseweb="tab"] {
    border-radius:8px 8px 0 0;
    padding:8px 16px;
    font-weight:500;
}
.st-expanderHeader {font-weight:600}
.stTextInput > div > div > input {border-radius:8px}
.stSlider > div {padding:0.3rem 0}
</style>
""", unsafe_allow_html=True)

# 全局实时接口拉取函数（缓存5分钟，防频繁请求）
@st.cache_data(ttl=300)
def get_quark_movie_ranking():
    if not api_token:
        return pd.DataFrame(), "❌ API密钥未配置，请检查.env配置文件"
    try:
        url = "https://api.istero.com/resource/v1/quark/film/top"
        headers = {"Authorization": f"Bearer {api_token}"}
        resp = requests.get(url, headers=headers, timeout=15)
        res_data = resp.json()
        if res_data.get("code") == 200:
            raw_list = res_data.get("data", [])
            df = pd.DataFrame(raw_list)
            # 数据类型清洗
            if "hot" in df.columns:
                df["hot"] = pd.to_numeric(df["hot"], errors="coerce")
            if "rank" in df.columns:
                df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
            # 拆分tag字段：提取年份、影片分类，用于多维度筛选统计
            def parse_tag(tag_str):
                if pd.isna(tag_str):
                    return None, None
                parts = str(tag_str).split("·")
                year = parts[0].strip() if len(parts)>=1 else "未知"
                genre = ",".join(parts[2:]) if len(parts)>=3 else "综合"
                return year, genre
            df[["年份","分类类型"]] = df["tag"].apply(lambda x: pd.Series(parse_tag(x)))
            return df, "✅ 夸克实时电影热榜拉取成功"
        else:
            msg = res_data.get("msg", "接口返回未知错误")
            return pd.DataFrame(), f"❌ 接口请求失败：{msg}"
    except Exception as e:
        return pd.DataFrame(), f"❌ 网络异常：{str(e)}"

df_raw, fetch_status = get_quark_movie_ranking()

# ====================== 侧边栏菜单（匹配你界面：数据概览/可视化分析/AI智能分析） ======================
with st.sidebar:
    st.title("📽️ 实时电影热榜分析系统")
    st.divider()
    st.info(f"接口连接状态：{fetch_status}")

    # 全局一键刷新实时数据
    refresh_btn = st.button("🔄 强制刷新实时榜单", use_container_width=True)
    if refresh_btn:
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("🔎 交互式筛选控制面板")

    df_filter = pd.DataFrame()
    if not df_raw.empty:
        # 热度区间滑块筛选
        min_hot = int(df_raw["hot"].min())
        max_hot = int(df_raw["hot"].max())
        hot_range = st.slider("热度区间筛选", min_hot, max_hot, (min_hot, max_hot), step=100)

        # 排名区间筛选
        min_rank = int(df_raw["rank"].min())
        max_rank = int(df_raw["rank"].max())
        rank_range = st.slider("排名区间筛选", min_rank, max_rank, (min_rank, max_rank))

        # 上映年份多选筛选
        year_list = sorted(df_raw["年份"].dropna().unique().tolist())
        year_select = st.multiselect("筛选上映年份", ["全部"] + year_list, default=["全部"])

        # 影片类型多选筛选
        type_list = sorted(df_raw["分类类型"].dropna().unique().tolist())
        type_select = st.multiselect("筛选影片类型", ["全部"] + type_list, default=["全部"])

        # 片名模糊搜索框
        keyword = st.text_input("影片名称模糊搜索", placeholder="输入片名过滤...")

        # 筛选逻辑，全局联动所有页面
        df_filter = df_raw.copy()
        df_filter = df_filter[(df_filter["hot"] >= hot_range[0]) & (df_filter["hot"] <= hot_range[1])]
        df_filter = df_filter[(df_filter["rank"] >= rank_range[0]) & (df_filter["rank"] <= rank_range[1])]
        if "全部" not in year_select and len(year_select) > 0:
            df_filter = df_filter[df_filter["年份"].isin(year_select)]
        if "全部" not in type_select and len(type_select) > 0:
            df_filter = df_filter[df_filter["分类类型"].isin(type_select)]
        if keyword.strip():
            df_filter = df_filter[df_filter["title"].str.contains(keyword, na=False, case=False)]

        st.divider()
        st.subheader("📄 数据导出交互")
        def export_csv(dataframe):
            buf = BytesIO()
            dataframe.to_csv(buf, index=False, encoding="utf-8-sig")
            buf.seek(0)
            return buf
        csv_buf = export_csv(df_filter)
        st.download_button(
            label="📥 导出当前筛选表格CSV",
            data=csv_buf,
            file_name="实时电影热榜筛选数据.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.warning("暂无榜单原始数据，筛选功能不可用")

    st.divider()
    st.subheader("📋 功能导航菜单")
    page_sel = st.radio("", [
        "数据概览",
        "可视化分析",
        "AI智能分析",
        "影片详情检索",
        "数据深度统计剖析"
    ])

# ====================== 页面1：数据概览 ======================
def page_overview():
    st.title("📊 数据概览 | 实时电影热榜大盘总览")
    if df_filter.empty:
        st.warning("当前筛选条件无匹配数据，请修改侧边栏筛选条件或刷新榜单")
        return

    st.subheader("📌 实时大盘核心统计指标卡片")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    total_cnt = len(df_filter)
    total_hot = df_filter["hot"].sum()
    avg_hot = round(df_filter["hot"].mean(), 0)
    max_hot_row = df_filter.loc[df_filter["hot"].idxmax()]
    min_hot_row = df_filter.loc[df_filter["hot"].idxmin()]

    c1.metric("筛选后影片总数", f"{total_cnt} 部")
    c2.metric("榜单总热度", f"{total_hot:,}")
    c3.metric("平均热度值", f"{avg_hot}")
    c4.metric("热度榜首影片", max_hot_row["title"])
    c5.metric("榜首热度数值", f"{max_hot_row['hot']:,}")
    c6.metric("热度最低影片", min_hot_row["title"])

    st.divider()
    st.subheader("📋 实时热榜明细表格（支持排序、滚动交互）")
    display_map = {
        "rank":"当前排名",
        "title":"影片名称",
        "hot":"热度值",
        "tag":"标签(年份/地区/类型)",
        "年份":"上映年份",
        "分类类型":"影片分类"
    }
    disp_df = df_filter[list(display_map.keys())].copy()
    disp_df.rename(columns=display_map, inplace=True)
    st.dataframe(disp_df, use_container_width=True, hide_index=True, height=450)

    st.divider()
    st.subheader("📐 数据质量审计（缺失值完整性检测）")
    audit_df = pd.DataFrame({
        "字段名": disp_df.columns,
        "非空数量": disp_df.notna().sum().values,
        "缺失数量": disp_df.isna().sum().values,
        "缺失率(%)": np.round((disp_df.isna().sum() / len(disp_df) * 100), 2)
    })
    st.dataframe(audit_df, use_container_width=True, hide_index=True)

# ====================== 页面2：可视化分析 ======================
def page_visual():
    st.title("📈 可视化分析 | 多维交互式热度可视化")
    if df_filter.empty:
        st.warning("当前筛选条件无匹配数据，请修改侧边栏筛选")
        return

    sort_opt = st.radio("图表排序切换", ["按热度降序","按热度升序"], horizontal=True)
    work_df = df_filter.copy()
    if sort_opt == "按热度降序":
        work_df = work_df.sort_values("hot", ascending=False)
    else:
        work_df = work_df.sort_values("hot", ascending=True)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "热度柱状排行图","热度分布直方图","Top10热度占比饼图",
        "排名-热度散点关联","年份热度汇总柱状","分类热度汇总柱状"
    ])

    with tab1:
        fig1 = px.bar(
            work_df, x="title", y="hot",
            title="全部影片热度排行柱状图",
            color="hot", color_continuous_scale="Blues",
            labels={"hot":"热度值","title":"影片名称"},
            hover_data=["rank","tag"]
        )
        fig1.update_layout(xaxis_tickangle=-45, height=550)
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        fig2 = px.histogram(
            work_df, x="hot", nbins=10,
            title="热度数值分布直方图",
            labels={"hot":"热度区间","count":"影片数量"}
        )
        fig2.update_layout(height=550)
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        top10 = work_df.head(10)
        fig3 = px.pie(
            top10, values="hot", names="title", hole=0.35,
            title="热度TOP10影片热度占比环形图"
        )
        fig3.update_layout(height=550)
        st.plotly_chart(fig3, use_container_width=True)

    with tab4:
        fig4 = px.scatter(
            work_df, x="rank", y="hot", hover_data=["title","tag"],
            title="排名与热度相关性散点图",
            labels={"rank":"榜单排名","hot":"热度值"}
        )
        fig4.update_layout(height=550)
        st.plotly_chart(fig4, use_container_width=True)

    with tab5:
        year_group = work_df.groupby("年份")["hot"].sum().reset_index()
        fig5 = px.bar(year_group, x="年份", y="hot", title="各年份总热度汇总")
        fig5.update_layout(height=550)
        st.plotly_chart(fig5, use_container_width=True)

    with tab6:
        type_group = work_df.groupby("分类类型")["hot"].sum().reset_index()
        fig6 = px.bar(type_group, x="分类类型", y="hot", title="各影片类型总热度汇总")
        fig6.update_layout(xaxis_tickangle=-45, height=550)
        st.plotly_chart(fig6, use_container_width=True)

# ====================== 页面3：AI智能分析 ======================
def page_ai_qa():
    st.title("🤖 AI智能分析 | 实时榜单自然语言问答交互系统")
    st.info("支持提问示例：\n1. 当前筛选后榜单总热度是多少？\n2. 热度排名前三的电影名称与热度\n3. 热度最高、热度最低分别是哪部影片\n4. 2025年上映所有影片热度总和\n5. 平均热度数值是多少")
    st.divider()

    question = st.text_area("请输入你的分析问题（基于实时筛选数据作答）", height=110, placeholder="在此输入你的问题...")
    ask_btn = st.button("🧠 提交问题，AI分析作答", type="primary")

    if ask_btn and question.strip():
        if df_filter.empty:
            st.error("当前筛选数据集为空，无法进行AI分析，请调整筛选条件")
            return
        total_cnt = len(df_filter)
        total_hot = df_filter["hot"].sum()
        avg_hot = round(df_filter["hot"].mean(), 2)
        max_hot_row = df_filter.loc[df_filter["hot"].idxmax()]
        min_hot_row = df_filter.loc[df_filter["hot"].idxmin()]
        top3_df = df_filter.sort_values("hot", ascending=False).head(3)
        top3_text = "\n".join([f"{i+1}.{row['title']}，热度{row['hot']}" for i,(_,row) in enumerate(top3_df.iterrows())])

        data_context = f"""
【实时热榜统计上下文】
筛选后影片总数：{total_cnt}部
榜单总热度：{total_hot:,}
平均热度：{avg_hot}
热度最高影片：{max_hot_row['title']}，热度{max_hot_row['hot']}，排名{max_hot_row['rank']}
热度最低影片：{min_hot_row['title']}，热度{min_hot_row['hot']}，排名{min_hot_row['rank']}
热度前三影片：
{top3_text}
完整明细数据：
{df_filter[['rank','title','hot','年份','分类类型','tag']].to_string(index=False)}
要求：严格使用上面给出实时数据回答，不能编造外部数据，回答条理清晰、简洁专业，适合数据分析作业使用。
用户问题：{question}
        """
        with st.spinner("AI正在解析实时榜单数据，生成专业分析回答..."):
            resp = Generation.call(
                model="qwen-turbo",
                prompt=data_context,
                result_format="message"
            )
            if resp.status_code == 200:
                st.success("✅ AI智能分析结果")
                st.markdown(resp.output.choices[0].message.content)
            else:
                st.error(f"大模型调用失败：{resp.message}")

# ====================== 页面4：影片详情检索【已完全删除所有跳转链接】 ======================
def page_detail_search():
    st.title("🔍 影片详情检索中心 | 单部影片明细查询")
    if df_filter.empty:
        st.warning("无匹配筛选数据")
        return
    if "title" not in df_filter.columns:
        st.error("接口缺失影片名称字段，检索功能不可用")
        return

    movie_list = df_filter["title"].tolist()
    select_movie = st.selectbox("选择指定影片查看完整详情", ["全部展开浏览"] + movie_list)

    if select_movie != "全部展开浏览":
        target = df_filter[df_filter["title"] == select_movie].iloc[0]
        with st.expander(f"🎬 {target['title']} 完整详情信息", expanded=True):
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("当前榜单排名", target["rank"])
            c2.metric("热度数值", f"{target['hot']:,}")
            c3.metric("上映年份", target["年份"])
            c4.metric("影片分类", target["分类类型"])
            st.markdown(f"**完整标签信息：** {target['tag']}")
    else:
        for _, row in df_filter.iterrows():
            rank_text = int(row["rank"]) if pd.notna(row["rank"]) else "未知"
            hot_text = f"{row['hot']:,}" if pd.notna(row["hot"]) else "未知"
            with st.expander(f"#{rank_text} | {row['title']} | 热度：{hot_text}"):
                col1,col2 = st.columns(2)
                col1.write(f"上映年份：{row.get('年份','未知')}")
                col1.write(f"影片分类：{row.get('分类类型','未知')}")
                col2.write(f"完整标签：{row.get('tag','暂无')}")

# ====================== 页面5：数据深度统计剖析 ======================
def page_stat_analysis():
    st.title("📑 数据深度统计剖析 | 描述统计与分组分析")
    if df_filter.empty:
        st.warning("暂无筛选数据集，无法统计分析")
        return

    st.subheader("热度值描述性统计（均值、中位数、四分位数、极值）")
    stat_df = df_filter["hot"].describe().reset_index()
    stat_df.columns = ["统计指标","对应数值"]
    st.dataframe(stat_df, use_container_width=True, hide_index=True)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("各上映年份影片数量统计")
        year_cnt = df_filter["年份"].value_counts().reset_index()
        year_cnt.columns = ["年份","影片数量"]
        fig_y = px.bar(year_cnt, x="年份", y="影片数量")
        st.plotly_chart(fig_y, use_container_width=True)
    with col2:
        st.subheader("各类型影片数量统计")
        type_cnt = df_filter["分类类型"].value_counts().reset_index()
        type_cnt.columns = ["分类类型","影片数量"]
        fig_t = px.bar(type_cnt, x="分类类型", y="影片数量")
        fig_t.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_t, use_container_width=True)

# 页面路由分发
if page_sel == "数据概览":
    page_overview()
elif page_sel == "可视化分析":
    page_visual()
elif page_sel == "AI智能分析":
    page_ai_qa()
elif page_sel == "影片详情检索":
    page_detail_search()
elif page_sel == "数据深度统计剖析":
    page_stat_analysis()