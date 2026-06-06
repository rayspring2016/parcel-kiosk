const API = getApp().globalData.API

Page({
  data: {
    packages: [],
    loading: true,
    userId: ""
  },

  async onLoad() {
    const userId = getApp().globalData.userId ||
                   dd.getStorageSync({ key: "userId" }).data || ""
    this.setData({ userId })
    await this.fetchPackages()
  },

  onShow() {
    this.fetchPackages()
  },

  async fetchPackages() {
    this.setData({ loading: true })
    try {
      const res = await dd.httpRequest({
        url: `${API}/my-packages?employee_id=${this.data.userId}`,
        method: "GET"
      })
      this.setData({ packages: res.data, loading: false })
    } catch (e) {
      dd.alert({ title: "加载失败", content: e.message || "请检查网络" })
      this.setData({ loading: false })
    }
  },

  async onPickup(e) {
    const pkgId = e.currentTarget.dataset.pkgid
    const code  = e.currentTarget.dataset.code
    try {
      await dd.httpRequest({
        url: `${API}/pickup/${pkgId}`,
        method: "POST"
      })
      dd.showToast({ content: `${code} 取件确认成功`, type: "success" })
      await this.fetchPackages()
    } catch (e) {
      dd.alert({ title: "操作失败", content: e.message || "请重试" })
    }
  }
})
