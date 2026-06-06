// API 地址集中在 globalData，两个页面不重复定义，修改一处即全局生效
App({
  globalData: {
    API: "http://your-server-ip:8000"
  }
})
