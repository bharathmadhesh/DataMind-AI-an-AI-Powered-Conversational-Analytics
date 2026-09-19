"""
Plotly charting module for Data Q&A.

Generates interactive charts (bar, line, scatter, or table) based on query
result DataFrames with smart column detection heuristics.
"""

from typing import List, Optional, Tuple
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _infer_chart_columns(
    df: pd.DataFrame,
    preferred_type: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Intelligently infer suitable X and Y axis columns from a DataFrame.
    
    Args:
        df: The pandas DataFrame.
        preferred_type: 'bar', 'line', or 'scatter'.
        
    Returns:
        Tuple of (x_col_name, y_col_name).
    """
    if df.empty or len(df.columns) == 0:
        return None, None

    cols = list(df.columns)
    if len(cols) == 1:
        # Single column: use index for X, column for Y
        return None, cols[0]

    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    non_numeric_cols = [c for c in cols if c not in numeric_cols]

    # Check for date-like columns among non-numeric
    date_cols = []
    for c in non_numeric_cols:
        lower_c = str(c).lower()
        if any(keyword in lower_c for keyword in ['date', 'time', 'year', 'month', 'day']):
            date_cols.append(c)

    if preferred_type == "line":
        # Line charts love dates or times on X, numeric on Y
        x_col = date_cols[0] if date_cols else (non_numeric_cols[0] if non_numeric_cols else cols[0])
        y_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])
        return x_col, y_col

    if preferred_type == "bar":
        # Bar charts: categorical on X, numeric on Y
        x_col = non_numeric_cols[0] if non_numeric_cols else cols[0]
        y_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])
        return x_col, y_col

    if preferred_type == "scatter":
        # Scatter: prefer two numeric columns
        if len(numeric_cols) >= 2:
            return numeric_cols[0], numeric_cols[1]
        x_col = cols[0]
        y_col = cols[1] if len(cols) > 1 else cols[0]
        return x_col, y_col

    # Default fallback
    return cols[0], cols[1] if len(cols) > 1 else cols[0]


from typing import Any, Dict, List, Optional, Tuple
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _infer_chart_columns(
    df: pd.DataFrame,
    preferred_type: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Intelligently infer suitable X and Y axis columns from a DataFrame.
    
    Args:
        df: The pandas DataFrame.
        preferred_type: 'bar', 'line', or 'scatter'.
        
    Returns:
        Tuple of (x_col_name, y_col_name).
    """
    if df.empty or len(df.columns) == 0:
        return None, None

    cols = list(df.columns)
    if len(cols) == 1:
        # Single column: use index for X, column for Y
        return None, cols[0]

    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    non_numeric_cols = [c for c in cols if c not in numeric_cols]

    # Check for date-like columns among non-numeric
    date_cols = []
    for c in non_numeric_cols:
        lower_c = str(c).lower()
        if any(keyword in lower_c for keyword in ['date', 'time', 'year', 'month', 'day']):
            date_cols.append(c)

    if preferred_type == "line":
        # Line charts love dates or times on X, numeric on Y
        x_col = date_cols[0] if date_cols else (non_numeric_cols[0] if non_numeric_cols else cols[0])
        y_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])
        return x_col, y_col

    if preferred_type == "bar":
        # Bar charts: categorical on X, numeric on Y
        x_col = non_numeric_cols[0] if non_numeric_cols else cols[0]
        y_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])
        return x_col, y_col

    if preferred_type == "scatter":
        # Scatter: prefer two numeric columns
        if len(numeric_cols) >= 2:
            return numeric_cols[0], numeric_cols[1]
        x_col = cols[0]
        y_col = cols[1] if len(cols) > 1 else cols[0]
        return x_col, y_col

    # Default fallback
    return cols[0], cols[1] if len(cols) > 1 else cols[0]


def build_chart(
    df: pd.DataFrame,
    chart_type: str,
    title: Optional[str] = None
) -> Optional[go.Figure]:
    """
    Create an upgraded Plotly figure from a DataFrame based on the requested chart type.
    
    Supports:
    - 'bar': Plotly Express px.bar with rounded corners, descending order, and outside labels
    - 'line': Plotly Express px.line with markers and hover
    - 'scatter': Plotly Express px.scatter
    - 'table': Plotly go.Table
    
    Args:
        df: DataFrame containing the query result.
        chart_type: Target chart type ('bar', 'line', 'scatter', 'table').
        title: Optional title for the chart.
        
    Returns:
        Plotly Figure object, or None if data is unsuitable for plotting.
    """
    if df is None or df.empty:
        return None

    clean_type = chart_type.strip().lower()
    MODERN_PALETTE = ["#6366F1", "#06B6D4", "#10B981", "#F59E0B", "#EC4899", "#8B5CF6"]

    # If table requested
    if clean_type == "table":
        header_values = [f"<b>{col}</b>" for col in df.columns]
        cell_values = [df[col].tolist() for col in df.columns]
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=header_values,
                fill_color='#1E293B',
                font=dict(color='#F8FAFC', size=12, family="Outfit, -apple-system, sans-serif"),
                align='left',
                line_color='rgba(255, 255, 255, 0.08)'
            ),
            cells=dict(
                values=cell_values,
                fill_color='#0F172A',
                font=dict(color='#E2E8F0', size=11, family="Inter, -apple-system, sans-serif"),
                align='left',
                height=28,
                line_color='rgba(255, 255, 255, 0.05)'
            )
        )])
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=35 if title else 10, b=10)
        )
        if title:
            fig.update_layout(
                title=dict(
                    text=title,
                    font=dict(color="#FFFFFF", size=15, family="Outfit, sans-serif")
                )
            )
        return fig

    x_col, y_col = _infer_chart_columns(df, clean_type)
    if y_col is None:
        return None

    try:
        plot_df = df.copy()
        is_currency = False
        if y_col:
            lower_y = str(y_col).lower()
            is_currency = any(kw in lower_y for kw in ['price', 'sale', 'cost', 'revenue', 'amount', 'total', 'dollar'])

        if clean_type == "line" and x_col:
            try:
                plot_df[x_col] = pd.to_datetime(plot_df[x_col])
                plot_df = plot_df.sort_values(by=x_col)
            except Exception:
                pass

        if clean_type == "bar":
            # 1. Aggregate if duplicate categories exist to prevent fragmented or stacked bars
            if x_col and y_col and x_col in plot_df.columns and y_col in plot_df.columns:
                if plot_df[x_col].duplicated().any():
                    plot_df = plot_df.groupby(x_col, as_index=False)[y_col].sum()
                # 2. Always sort descending so highest bar is first on the left
                plot_df = plot_df.sort_values(by=y_col, ascending=False)

            fig = px.bar(
                plot_df,
                x=x_col,
                y=y_col,
                title=title,
                template="plotly_dark",
                color_discrete_sequence=MODERN_PALETTE
            )
            val_format = "$%{y:,.2s}" if is_currency else "%{y:,.2s}"
            hover_val = "$%{y:,.2f}" if is_currency else "%{y:,.2f}"
            fig.update_traces(
                texttemplate=val_format,
                textposition="outside",
                marker=dict(cornerradius=8),
                hovertemplate=f"<b style='font-size:13px;'>%{{x}}</b><br><span style='color:#94A3B8;'>{y_col}:</span> <b style='color:#818CF8;'>{hover_val}</b><extra></extra>"
            )
        elif clean_type == "line":
            fig = px.line(
                plot_df,
                x=x_col,
                y=y_col,
                title=title,
                markers=True,
                template="plotly_dark",
                color_discrete_sequence=MODERN_PALETTE
            )
            hover_val = "$%{y:,.2f}" if is_currency else "%{y:,.2f}"
            fig.update_traces(
                hovertemplate=f"<b style='font-size:13px;'>%{{x}}</b><br><span style='color:#94A3B8;'>{y_col}:</span> <b style='color:#818CF8;'>{hover_val}</b><extra></extra>"
            )
        elif clean_type == "scatter":
            fig = px.scatter(
                plot_df,
                x=x_col,
                y=y_col,
                title=title,
                template="plotly_dark",
                color_discrete_sequence=MODERN_PALETTE
            )
        else:
            fig = px.bar(
                plot_df,
                x=x_col,
                y=y_col,
                title=title,
                template="plotly_dark",
                color_discrete_sequence=MODERN_PALETTE
            )

        layout_kwargs = dict(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(19, 27, 46, 0.4)",
            font=dict(family="Inter, -apple-system, sans-serif", color="#F3F4F6", size=12),
            title=dict(
                font=dict(family="Outfit, -apple-system, sans-serif", color="#FFFFFF", size=16)
            ) if title else None,
            xaxis=dict(
                gridcolor="rgba(255, 255, 255, 0.08)",
                zerolinecolor="rgba(255, 255, 255, 0.12)",
                linecolor="rgba(255, 255, 255, 0.12)",
                tickfont=dict(color="#9CA3AF")
            ),
            yaxis=dict(
                gridcolor="rgba(255, 255, 255, 0.08)",
                zerolinecolor="rgba(255, 255, 255, 0.12)",
                linecolor="rgba(255, 255, 255, 0.12)",
                tickfont=dict(color="#9CA3AF")
            ),
            margin=dict(l=20, r=20, t=45 if title else 20, b=20),
            hovermode="x unified" if clean_type != "scatter" else "closest"
        )
        if clean_type == "bar":
            layout_kwargs["xaxis"]["categoryorder"] = "total descending"

        fig.update_layout(**layout_kwargs)
        return fig
    except Exception:
        return None


def build_echarts_html(
    df: pd.DataFrame,
    chart_type: str,
    title: Optional[str] = None,
    height: int = 380
) -> Optional[str]:
    """
    Generate a responsive, highly-engaging Apache ECharts 5 HTML visualization.
    
    Provides ChatGPT/Claude-style visual interactivity:
    - Magnetic shadow axisPointer that highlights columns as you drag/hover near bars
    - Floating glassmorphic tooltip card showing exact formatted amounts (e.g. $46,132.34)
    - Sleek linear gradients and rounded bar crowns
    - Direct data labels on top of bars
    - Built-in toolbox (Download Image, Data View, Zoom, Switch between Bar & Line)
    
    Args:
        df: Query result DataFrame.
        chart_type: 'bar', 'line', 'scatter', or 'table'.
        title: Optional chart title.
        height: Pixel height of container.
        
    Returns:
        Self-contained HTML string embedding Apache ECharts 5 via CDN, or None.
    """
    if df is None or df.empty:
        return None

    clean_type = chart_type.strip().lower()
    if clean_type == "table":
        return None

    x_col, y_col = _infer_chart_columns(df, clean_type)
    if y_col is None:
        return None

    try:
        plot_df = df.copy()
        lower_y = str(y_col).lower()
        is_currency = any(kw in lower_y for kw in ['price', 'sale', 'cost', 'revenue', 'amount', 'total', 'dollar'])

        if clean_type == "bar":
            # 1. Deduplicate/aggregate if multiple rows have the same category
            if x_col and y_col and x_col in plot_df.columns and y_col in plot_df.columns:
                if plot_df[x_col].duplicated().any():
                    plot_df = plot_df.groupby(x_col, as_index=False)[y_col].sum()
                # 2. Always sort descending so highest bar is first on the left
                plot_df = plot_df.sort_values(by=y_col, ascending=False)
        elif clean_type == "line" and x_col:
            try:
                plot_df[x_col] = pd.to_datetime(plot_df[x_col])
                plot_df = plot_df.sort_values(by=x_col)
            except Exception:
                pass

        x_vals = plot_df[x_col].astype(str).tolist() if x_col else [str(i) for i in range(len(plot_df))]
        y_vals = [float(v) if pd.notnull(v) else 0.0 for v in plot_df[y_col]]

        # Base ECharts options
        options: Dict[str, Any] = {
            "backgroundColor": "transparent",
            "animation": True,
            "animationDuration": 900,
            "animationEasing": "cubicOut",
            "grid": {
                "left": "3%",
                "right": "4%",
                "bottom": "8%",
                "top": "16%" if title else "10%",
                "containLabel": True
            },
            "toolbox": {
                "show": True,
                "right": "3%",
                "top": "2%",
                "iconStyle": {
                    "borderColor": "#94A3B8"
                },
                "feature": {
                    "magicType": {"show": True, "type": ["bar", "line"]},
                    "dataView": {"show": True, "readOnly": True, "title": "Data View"},
                    "saveAsImage": {"show": True, "title": "Save PNG", "pixelRatio": 2}
                }
            }
        }

        if title:
            options["title"] = {
                "text": title,
                "left": "left",
                "top": "2%",
                "textStyle": {
                    "color": "#F8FAFC",
                    "fontFamily": "Outfit, system-ui, sans-serif",
                    "fontSize": 15,
                    "fontWeight": 600
                }
            }

        # Configure X Axis
        options["xAxis"] = {
            "type": "category",
            "data": x_vals,
            "axisLine": {"lineStyle": {"color": "rgba(255, 255, 255, 0.12)"}},
            "axisTick": {"show": False},
            "axisLabel": {
                "color": "#94A3B8",
                "fontFamily": "Inter, system-ui, sans-serif",
                "fontSize": 12,
                "interval": 0,
                "rotate": 25 if len(x_vals) > 5 else 0
            }
        }

        # Configure Y Axis
        options["yAxis"] = {
            "type": "value",
            "splitLine": {"lineStyle": {"color": "rgba(255, 255, 255, 0.06)", "type": "dashed"}},
            "axisLine": {"show": False},
            "axisTick": {"show": False},
            "axisLabel": {
                "color": "#64748B",
                "fontFamily": "Inter, system-ui, sans-serif",
                "fontSize": 11
            }
        }

        # Configure Series based on Chart Type
        if clean_type == "line":
            options["tooltip"] = {
                "trigger": "axis",
                "axisPointer": {"type": "cross", "crossStyle": {"color": "#6366F1"}},
                "backgroundColor": "rgba(15, 23, 42, 0.95)",
                "borderColor": "rgba(99, 102, 241, 0.4)",
                "borderWidth": 1,
                "padding": [10, 14],
                "textStyle": {"color": "#F8FAFC", "fontFamily": "Inter, system-ui, sans-serif"},
                "extraCssText": "box-shadow: 0 12px 32px rgba(0,0,0,0.6); border-radius: 10px; backdrop-filter: blur(10px);"
            }
            options["series"] = [{
                "name": str(y_col),
                "type": "line",
                "data": y_vals,
                "smooth": True,
                "symbol": "circle",
                "symbolSize": 8,
                "itemStyle": {"color": "#818CF8"},
                "lineStyle": {"width": 3, "color": "#6366F1"},
                "areaStyle": {
                    "color": {
                        "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "rgba(99, 102, 241, 0.45)"},
                            {"offset": 1, "color": "rgba(99, 102, 241, 0.02)"}
                        ]
                    }
                }
            }]
        elif clean_type == "scatter":
            options["tooltip"] = {
                "trigger": "item",
                "backgroundColor": "rgba(15, 23, 42, 0.95)",
                "borderColor": "rgba(99, 102, 241, 0.4)",
                "borderWidth": 1,
                "padding": [10, 14],
                "textStyle": {"color": "#F8FAFC", "fontFamily": "Inter, system-ui, sans-serif"}
            }
            options["series"] = [{
                "name": str(y_col),
                "type": "scatter",
                "data": y_vals,
                "symbolSize": 12,
                "itemStyle": {
                    "color": "#818CF8",
                    "shadowBlur": 10,
                    "shadowColor": "rgba(99, 102, 241, 0.6)"
                }
            }]
        else:
            # Bar Chart: magnetic shadow pointer + glowing gradient + outside labels
            options["tooltip"] = {
                "trigger": "axis",
                "axisPointer": {
                    "type": "shadow",
                    "shadowStyle": {"color": "rgba(99, 102, 241, 0.12)"}
                },
                "backgroundColor": "rgba(15, 23, 42, 0.95)",
                "borderColor": "rgba(99, 102, 241, 0.4)",
                "borderWidth": 1,
                "padding": [10, 14],
                "textStyle": {"color": "#F8FAFC", "fontFamily": "Inter, system-ui, sans-serif"},
                "extraCssText": "box-shadow: 0 12px 32px rgba(0,0,0,0.6); border-radius: 10px; backdrop-filter: blur(10px);"
            }
            options["series"] = [{
                "name": str(y_col),
                "type": "bar",
                "data": y_vals,
                "barMaxWidth": 54,
                "itemStyle": {
                    "borderRadius": [8, 8, 2, 2],
                    "color": {
                        "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "#818CF8"},
                            {"offset": 1, "color": "#4F46E5"}
                        ]
                    }
                },
                "emphasis": {
                    "itemStyle": {
                        "color": {
                            "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                            "colorStops": [
                                {"offset": 0, "color": "#38BDF8"},
                                {"offset": 1, "color": "#6366F1"}
                            ]
                        },
                        "shadowBlur": 16,
                        "shadowColor": "rgba(99, 102, 241, 0.6)"
                    }
                }
            }]

        options_json = json.dumps(options)
        is_curr_js = "true" if is_currency else "false"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body, html {{ width: 100%; height: 100%; overflow: hidden; background: transparent; }}
    #echarts-box {{
      width: 100%;
      height: {height}px;
      background: rgba(19, 27, 46, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 6px;
    }}
  </style>
</head>
<body>
  <div id="echarts-box"></div>
  <script>
    (function() {{
      var chartDom = document.getElementById('echarts-box');
      var myChart = echarts.init(chartDom, 'dark', {{ renderer: 'canvas' }});
      var option = {options_json};
      var isCurrency = {is_curr_js};

      // Enhanced magnetic tooltip formatter with currency styling & badge
      if (option.tooltip) {{
        option.tooltip.formatter = function(params) {{
          var p = Array.isArray(params) ? params[0] : params;
          var val = p.value;
          var formattedVal = (typeof val === 'number')
            ? (isCurrency ? '$' + val.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}}) : val.toLocaleString('en-US'))
            : val;
          return '<div style="font-size:11px; color:#94A3B8; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:4px;">' + (p.name || '') + '</div>' +
                 '<div style="font-size:16px; font-weight:700; color:#818CF8; display:flex; align-items:center; gap:8px;">' +
                 '<span style="display:inline-block; width:9px; height:9px; border-radius:50%; background:#6366F1; box-shadow: 0 0 10px #6366F1;"></span>' +
                 formattedVal + '</div>';
        }};
      }}

      // Top labels for bars
      if (option.series && option.series[0] && option.series[0].type === 'bar') {{
        option.series[0].label = {{
          show: true,
          position: 'top',
          color: '#94A3B8',
          fontFamily: 'Inter, system-ui, sans-serif',
          fontSize: 11,
          formatter: function(p) {{
            if (typeof p.value !== 'number') return p.value;
            var prefix = isCurrency ? '$' : '';
            if (Math.abs(p.value) >= 1000000) return prefix + (p.value / 1000000).toFixed(1) + 'M';
            if (Math.abs(p.value) >= 1000) return prefix + (p.value / 1000).toFixed(1) + 'k';
            return prefix + p.value.toLocaleString();
          }}
        }};
      }}

      // Y-axis label compact formatting
      if (option.yAxis) {{
        option.yAxis.axisLabel.formatter = function(val) {{
          if (typeof val !== 'number') return val;
          var prefix = isCurrency ? '$' : '';
          if (Math.abs(val) >= 1000000) return prefix + (val / 1000000).toFixed(1) + 'M';
          if (Math.abs(val) >= 1000) return prefix + (val / 1000).toFixed(0) + 'k';
          return prefix + val;
        }};
      }}

      myChart.setOption(option);

      // Smooth auto-resize on window / container resize
      window.addEventListener('resize', function() {{
        myChart.resize();
      }});
    }})();
  </script>
</body>
</html>
"""
        return html_content.strip()
    except Exception:
        return None

