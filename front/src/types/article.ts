// 文章类型枚举
export enum ArticleType {
  NEWS = "news",
  INTERPRETATION = "interpretation"
}

// 文章状态枚举
export enum ArticleStatus {
  DRAFT = "draft",
  PUBLISHED = "published",
  OFFLINE = "offline"
}

// 分类类型
export interface Category {
  id: number;
  name: string;
  code: string;
  sort_order: number;
}

// 文章类型
export interface Article {
  id: number;
  title: string;
  summary?: string;
  content: string;
  cover_image?: string;
  category_id: number;
  type: ArticleType;
  status: ArticleStatus;
  source_name: string;
  origin_url?: string;
  publish_date: string;
  is_vectorized: boolean;
  view_count: number;
  category?: Category;
  /** 所属新闻ID，仅解读类型有值 */
  news_id?: number | null;
}

// 收藏类型
export interface Favorite {
  id: number;
  user_id: number;
  article_id: number;
  created_at: string;
}

// 响应类型
export interface ArticleListResponse {
  code: number;
  message: string;
  data: {
    items: Article[];
    total: number;
    page: number;
    page_size: number;
  };
}

export interface ArticleResponse {
  code: number;
  message: string;
  data: Article;
}

export interface CategoryListResponse {
  code: number;
  message: string;
  data: Category[];
}
