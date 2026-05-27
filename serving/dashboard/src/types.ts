/**
 * Types and Interfaces for Drama Intelligence Dashboard
 */

export interface CommentStats {
  total_raw: number;
  total_clean: number;
  total_trash: number;
  trash_rate: string;
}

export interface StanceDistribution {
  [key: string]: {
    count: number;
    percent: string;
  };
}

export interface TopEvent {
  id_content: string;
  ten_su_kien: string;
  time_event: string;
  total: number;
  clean: number;
  trash: number;
}

export interface CategoryData {
  category: string;
  total_events: number;
  events_with_analysis: number;
  events_without_analysis?: number;
  total_links: number;
  comment_stats: CommentStats;
  stance_distribution?: StanceDistribution;
  emotion_distribution?: StanceDistribution;
  top_events_by_comments: TopEvent[];
  events_by_year: Record<string, number>;
}

export interface OverallStats {
  total_events: number;
  total_events_with_analysis: number;
  total_events_without_analysis: number;
  total_links: number;
  total_links_website?: number;
  total_links_facebook?: number;
  total_comments: {
    raw: number;
    clean: number;
    trash: number;
    trash_rate: string;
  };
  by_category: {
    education: { events: number; comments_clean: number };
    showbiz: { events: number; comments_clean: number };
  };
}

export interface InsightsData {
  overall: OverallStats;
  education: CategoryData;
  showbiz: CategoryData;
}
